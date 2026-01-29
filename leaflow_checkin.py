#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 (流程修正版：启动台 -> 跳转 -> 签到页)
"""

import os
import time
import logging
import random
import html
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('selenium').setLevel(logging.ERROR)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        chrome_options = Options()
        # --- 核心配置 ---
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 关键：Eager模式，防止页面一直在转圈加载导致脚本卡死
        chrome_options.set_capability("pageLoadStrategy", "eager")
        
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 路径查找
        if os.path.exists("/usr/bin/chromium"):
            chrome_options.binary_location = "/usr/bin/chromium"
        elif os.path.exists("/usr/bin/chromium-browser"):
            chrome_options.binary_location = "/usr/bin/chromium-browser"

        driver_path = "/usr/bin/chromedriver"
        if not os.path.exists(driver_path):
             driver_path = "/usr/lib/chromium/chromedriver"

        try:
            service = Service(executable_path=driver_path) if os.path.exists(driver_path) else None
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            # 设置超时，防止无限等待
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise e

    def js_click(self, element):
        """使用JS点击，比原生点击更稳"""
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except: return False

    def login(self):
        logger.info(f"正在登录: {self.email[:3]}***")
        self.driver.get("https://leaflow.net/login")
        time.sleep(5)
        
        try:
            # 清理弹窗
            self.driver.execute_script("document.querySelector('.ant-modal-root')?.remove()")

            # 1. 输入账号 (ID #account)
            try:
                email_input = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "account")))
            except:
                email_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            
            self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
            
            # 2. 输入密码 (ID password)
            try:
                pass_input = self.driver.find_element(By.ID, "password")
            except:
                pass_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            self.driver.execute_script("arguments[0].value = arguments[1];", pass_input, self.password)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", pass_input)
            
            # 3. 点击登录
            time.sleep(1)
            try:
                login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                login_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), '登录')]")
            self.js_click(login_btn)
            
            # 4. 验证
            WebDriverWait(self.driver, 25).until(lambda d: "login" not in d.current_url)
            logger.info("登录成功")
            return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False

    def checkin(self):
        # 1. 先去启动台 (Launchpad)
        logger.info("前往启动台寻找入口...")
        self.driver.get("https://leaflow.net/launchpad")
        time.sleep(8)
        
        if "Just a moment" in self.driver.title:
            return False, "在启动台被拦截"

        try:
            # --- 第一步：点击启动台上的“签到” ---
            logger.info("寻找启动台上的【签到】图标...")
            entry_btn = None
            # 查找所有包含“签到”文字的元素
            xpaths = [
                "//div[contains(text(), '签到')]",
                "//span[contains(text(), '签到')]",
                "//h3[contains(text(), '签到')]",
                "//p[contains(text(), '签到')]"
            ]
            for xp in xpaths:
                try:
                    els = self.driver.find_elements(By.XPATH, xp)
                    for el in els:
                        if el.is_displayed():
                            entry_btn = el
                            break
                    if entry_btn: break
                except: continue
            
            if not entry_btn:
                # 再次确认是否已签到
                if "已签到" in self.driver.page_source:
                    return True, "今日已签到 (启动台显示)"
                return False, "未在启动台找到签到入口"

            # 记录当前窗口句柄，点击后可能会打开新标签页
            original_window = self.driver.current_window_handle
            self.js_click(entry_btn)
            logger.info("已点击入口，等待跳转...")
            time.sleep(5)

            # --- 第二步：处理跳转/新标签页 ---
            # 检查是否有新窗口打开
            if len(self.driver.window_handles) > 1:
                logger.info("检测到新窗口，正在切换...")
                for window_handle in self.driver.window_handles:
                    if window_handle != original_window:
                        self.driver.switch_to.window(window_handle)
                        break
            else:
                logger.info("未检测到新窗口，继续在当前页查找...")

            # 此时应该在 checkin.leaflow.net 了
            logger.info(f"当前页面: {self.driver.title}")
            
            # 再次检查 Cloudflare
            if "Just a moment" in self.driver.title:
                return False, "跳转后被Cloudflare拦截"

            # --- 第三步：点击真正的“立即签到”按钮 ---
            logger.info("寻找最终的【立即签到】按钮...")
            
            # 先检查是否已经签到
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "已签到" in body_text or "明日再来" in body_text:
                return True, "今日已签到"

            # 查找按钮
            targets = [
                (By.CSS_SELECTOR, "button.checkin-btn"),
                (By.CSS_SELECTOR, "button.btn-primary"),
                (By.XPATH, "//button[contains(text(), '签到')]"),
                (By.XPATH, "//button[contains(text(), 'Check')]")
            ]
            
            final_btn = None
            for by, val in targets:
                try:
                    btn = self.driver.find_element(by, val)
                    if btn.is_displayed():
                        final_btn = btn
                        break
                except: continue
            
            if final_btn:
                self.js_click(final_btn)
                logger.info("点击了最终签到按钮")
                time.sleep(5)
                
                # --- 第四步：获取结果 ---
                res_source = self.driver.find_element(By.TAG_NAME, "body").text
                match = re.search(r'(获得|奖励)\s?(\d+\.?\d*)\s?元', res_source)
                if match:
                    return True, f"签到成功！获得 {match.group(2)} 元"
                if "成功" in res_source:
                    return True, "签到成功！"
                
                return True, "签到动作已执行"
            
            return False, "未找到最终签到按钮"

        except Exception as e:
            return False, f"流程异常: {str(e)[:50]}"

    def get_balance(self):
        try:
            # 回到 Dashboard 或 Launchpad 看余额
            self.driver.get("https://leaflow.net/launchpad")
            time.sleep(5)
            text = self.driver.page_source
            amounts = re.findall(r'[¥￥]\s?(\d{1,4}\.\d{2})', text)
            if amounts:
                return f"{amounts[0]}元"
            return "获取失败"
        except:
            return "0"

    def run(self):
        try:
            if self.login():
                success, msg = self.checkin()
                balance = self.get_balance()
                return success, msg, balance
            return False, "登录失败", "0"
        except Exception as e:
            return False, f"异常: {str(e)}", "0"
        finally:
            if self.driver: self.driver.quit()

class MultiAccountManager:
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = []
        acc_str = os.getenv('LEAFLOW_ACCOUNTS', '')
        for pair in acc_str.split(','):
            if ':' in pair:
                e, p = pair.split(':', 1)
                self.accounts.append({'email': e.strip(), 'password': p.strip()})

    def send_notification(self, success_count, total_count, results):
        date_str = datetime.now().strftime("%Y/%m/%d")
        msg = "🎁 Leaflow自动签到通知\n"
        msg += f"📊 成功: {success_count}/{total_count}\n"
        msg += f"📅 签到时间：{date_str}\n\n"
        
        for res in results:
            email_masked = res['email']
            if '@' in email_masked:
                parts = email_masked.split('@')
                email_masked = f"{parts[0][:3]}***@{parts[1]}" if len(parts[0]) > 3 else f"{parts[0]}***@{parts[1]}"
            
            msg += f"账号：{email_masked}\n"
            if res['success']:
                clean_msg = res['msg'].replace("签到成功！", "").strip()
                msg += f"✅  签到成功！{clean_msg}\n" if "获得" in res['msg'] else f"✅  {res['msg']}\n"
                msg += f"💰  当前总余额：{res['balance']}。\n"
            else:
                msg += f"❌  签到失败\n⚠️  原因：{html.escape(str(res['msg']))}\n"
            msg += "\n"
        
        print(msg)
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                data = {"chat_id": self.telegram_chat_id, "text": msg, "parse_mode": "HTML"}
                requests.post(url, data=data, timeout=10)
            except: pass

    def run_all(self):
        results = []
        success_count = 0
        for i, acc in enumerate(self.accounts):
            print(f"=== 正在处理账号 {i+1} ===")
            try:
                bot = LeaflowAutoCheckin(acc['email'], acc['password'])
                is_success, msg, bal = bot.run()
                if is_success: success_count += 1
                results.append({"email": acc['email'], "success": is_success, "msg": msg, "balance": bal})
            except Exception as e:
                results.append({"email": acc['email'], "success": False, "msg": f"脚本崩溃: {e}", "balance": "0"})
            
            if i < len(self.accounts) - 1:
                wait = random.randint(15, 30)
                print(f"等待 {wait} 秒...")
                time.sleep(wait)
        self.send_notification(success_count, len(self.accounts), results)

if __name__ == "__main__":
    MultiAccountManager().run_all()
