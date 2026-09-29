# Suno AI - NVDA Voice Assistant v1.9.1
import globalPluginHandler
import ui
import core
import threading
import time
import os
import datetime
import urllib.request
import urllib.parse
import json
import subprocess
import ctypes
import array
import winsound
import re
import config
import gui
import wx
from gui.settingsDialogs import SettingsPanel

confspec = {
    "wake_word": "string(default='hey suno')",
    "sensitivity": "integer(min=30, max=99, default=85)",
    "last_version": "string(default='1.0.0')",
    "custom_commands": "string_list(default=list())",
    "show_response_box": "boolean(default=False)",
    "spoken_language": "string(default='ur-PK')",
    "translated_language": "string(default='en')"
}
config.conf.spec["suno_ai"] = confspec

class SunoAISettingsPanel(SettingsPanel):
    title = "Suno AI"
    
    def makeSettings(self, settingsSizer):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        ww_label = wx.StaticText(self, label="&Custom Wake Word:")
        self.ww_edit = wx.TextCtrl(self, value=config.conf["suno_ai"]["wake_word"])
        
        sens_label = wx.StaticText(self, label="&Wake Word Strictness (30 to 99, default 85):")
        self.sens_slider = wx.Slider(self, value=config.conf["suno_ai"]["sensitivity"], minValue=30, maxValue=99, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        
        cmd_label = wx.StaticText(self, label="&Custom Commands (Format: voice phrase = path/url):")
        cmds_str = "\n".join(config.conf["suno_ai"]["custom_commands"])
        self.cmd_edit = wx.TextCtrl(self, style=wx.TE_MULTILINE, value=cmds_str)
        
        sl_label = wx.StaticText(self, label="&Spoken Language Code (e.g. ur-PK, en-US, hi-IN):")
        self.sl_edit = wx.TextCtrl(self, value=config.conf["suno_ai"]["spoken_language"])
        
        tl_label = wx.StaticText(self, label="&Translated Language Code (e.g. en, ur, hi):")
        self.tl_edit = wx.TextCtrl(self, value=config.conf["suno_ai"]["translated_language"])
        
        self.show_box_cb = wx.CheckBox(self, label="S&how AI responses in a readable text box")
        self.show_box_cb.SetValue(config.conf["suno_ai"]["show_response_box"])
        
        sizer.Add(ww_label)
        sizer.Add(self.ww_edit, 0, wx.EXPAND | wx.BOTTOM, 10)
        sizer.Add(sens_label)
        sizer.Add(self.sens_slider, 0, wx.EXPAND | wx.BOTTOM, 10)
        sizer.Add(sl_label)
        sizer.Add(self.sl_edit, 0, wx.EXPAND | wx.BOTTOM, 10)
        sizer.Add(tl_label)
        sizer.Add(self.tl_edit, 0, wx.EXPAND | wx.BOTTOM, 10)
        sizer.Add(cmd_label)
        sizer.Add(self.cmd_edit, 1, wx.EXPAND | wx.BOTTOM, 10)
        sizer.Add(self.show_box_cb, 0, wx.BOTTOM, 10)
        
        settingsSizer.Add(sizer, 0, wx.EXPAND)
        
    def onSave(self):
        config.conf["suno_ai"]["wake_word"] = self.ww_edit.GetValue().strip().lower()
        config.conf["suno_ai"]["sensitivity"] = self.sens_slider.GetValue()
        config.conf["suno_ai"]["show_response_box"] = self.show_box_cb.GetValue()
        config.conf["suno_ai"]["spoken_language"] = self.sl_edit.GetValue().strip()
        config.conf["suno_ai"]["translated_language"] = self.tl_edit.GetValue().strip()
        
        cmds = []
        for line in self.cmd_edit.GetValue().split('\n'):
            line = line.strip()
            if line and "=" in line:
                cmds.append(line)
        config.conf["suno_ai"]["custom_commands"] = cmds
        
        for plugin in globalPluginHandler.runningPlugins:
            if type(plugin).__name__ == "GlobalPlugin" and hasattr(plugin, "restart_wakeword_process"):
                plugin.restart_wakeword_process()
                break

gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SunoAISettingsPanel)

def translate_text_api(text, sl, tl):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={urllib.parse.quote(text)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.loads(r.read().decode('utf-8'))
            return "".join([x[0] for x in res[0]])
    except Exception as e:
        return ""

class TranslationFrame(wx.Frame):
    def __init__(self, parent, title):
        super(TranslationFrame, self).__init__(parent, title=title, size=(600, 400))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        vbox.Add(self.text_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizer(vbox)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.is_active = True
        self.Show()
        self.Raise()
        self.text_ctrl.SetFocus()

    def append_text(self, text):
        self.text_ctrl.AppendText(text + "\n")

    def OnClose(self, event):
        self.is_active = False
        event.Skip()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "Suno AI"
    
    __gestures__ = {
        "kb:nvda+shift+w": "toggleSleepMode",
        "kb:nvda+shift+s": "startListening",
    }
    
    def __init__(self, *args, **kwargs):
        super(GlobalPlugin, self).__init__(*args, **kwargs)
        self.wakeword_process = None
        self.keep_running = True
        self.pause_wakeword = False
        self.winmm = ctypes.windll.winmm
        self.lock_path = os.path.join(os.getenv("TEMP"), "suno_pause.lock")
        
        current_version = "2.2.1"
        if config.conf["suno_ai"]["last_version"] != current_version:
            config.conf["suno_ai"]["last_version"] = current_version
            msg = (
                "Welcome to Suno AI Voice Assistant v2.2.1!\n\n"
                "What's New:\n"
                "1. Live Voice Translation: Say 'Start voice translation' to open a dictation box. Speak in your language and it will be translated and typed automatically! You can change the Spoken and Translated languages in NVDA Settings -> Suno AI.\n"
                "2. Copyable Responses: You can enable a text box for AI responses in settings.\n"
                "3. Take Screenshots: Say 'Take a screenshot'.\n"
                "4. Take Pictures: Say 'Take a picture'.\n"
                "5. System Info: Say 'Device info', 'Storage info', or 'RAM info'.\n\n"
                "Join Suno Tech Solutions Community on WhatsApp:\n"
                "https://chat.whatsapp.com/E5yVVf0UY7l5pHGDDYdzFy"
            )
            core.callLater(2000, ui.browseableMessage, msg, "Suno AI Update")
            
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except:
            pass
            
        threading.Thread(target=self._run_wakeword_process).start()

    def terminate(self):
        self.keep_running = False
        if self.wakeword_process:
            try:
                self.wakeword_process.kill()
            except:
                pass
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except:
            pass
        if hasattr(self, 'translation_frame') and self.translation_frame:
            try:
                wx.CallAfter(self.translation_frame.Close)
            except:
                pass
        super(GlobalPlugin, self).terminate()

    def _translation_loop(self):
        sl = config.conf["suno_ai"]["spoken_language"]
        tl = config.conf["suno_ai"]["translated_language"]
        
        # Lock the microphone so wake word doesn't interfere
        self.pause_wakeword = True
        try:
            with open(self.lock_path, "w") as f:
                f.write("1")
        except:
            pass
            
        while hasattr(self, 'translation_frame') and self.translation_frame and getattr(self.translation_frame, 'is_active', False):
            wav_path = os.path.join(os.getenv("TEMP"), f"suno_trans_{int(time.time())}.wav")
            self.winmm.mciSendStringW("close capture", None, 0, None)
            self.winmm.mciSendStringW("open new type waveaudio alias capture", None, 0, None)
            self.winmm.mciSendStringW("record capture", None, 0, None)
            
            for _ in range(50):
                if not getattr(self.translation_frame, 'is_active', False):
                    break
                time.sleep(0.1)
                
            self.winmm.mciSendStringW("stop capture", None, 0, None)
            self.winmm.mciSendStringW(f"save capture \"{wav_path}\"", None, 0, None)
            self.winmm.mciSendStringW("close capture", None, 0, None)
            
            if os.path.exists(wav_path):
                try:
                    with open(wav_path, "rb") as f:
                        audio_data = f.read()
                    os.remove(wav_path)
                    
                    text = self._recognize_google(audio_data, lang=sl)
                    if text:
                        translated = translate_text_api(text, sl, tl)
                        if translated and hasattr(self, 'translation_frame') and getattr(self.translation_frame, 'is_active', False):
                            wx.CallAfter(self.translation_frame.append_text, f"{text}\n-> {translated}\n")
                except:
                    pass
                    
        # Release the microphone lock
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except:
            pass
        self.pause_wakeword = False

    def start_voice_translation(self):
        if hasattr(self, 'translation_frame'):
            del self.translation_frame
            
        def _open_frame():
            try:
                self.translation_frame = TranslationFrame(None, "Suno AI Live Translation")
            except Exception as e:
                pass
        wx.CallAfter(_open_frame)
        
        def _run_loop():
            for _ in range(50):
                if hasattr(self, 'translation_frame') and getattr(self.translation_frame, 'is_active', False):
                    break
                time.sleep(0.1)
            self._translation_loop()
            
        threading.Thread(target=_run_loop).start()

    def script_startListening(self, gesture):
        if self.pause_wakeword:
            return
        
        self.pause_wakeword = True
        
        try:
            with open(self.lock_path, "w") as f:
                f.write("1")
        except:
            pass
                
        threading.Thread(target=self._listen_and_process).start()

    script_startListening.__doc__ = "Starts listening for Suno AI voice commands."
    script_startListening.category = "Suno AI"

    def _recognize_google(self, audio_data, lang="en-US"):
        if len(audio_data) <= 44:
            return None
            
        channels = int.from_bytes(audio_data[22:24], 'little')
        rate = int.from_bytes(audio_data[24:28], 'little')
        bits = int.from_bytes(audio_data[34:36], 'little')
        
        raw_pcm = audio_data[44:]
        
        if bits == 8:
            samples_8bit = array.array('B', raw_pcm)
            samples_16bit = array.array('h', ((x - 128) * 256 for x in samples_8bit))
            raw_16bit = samples_16bit.tobytes()
        elif bits == 16:
            raw_16bit = raw_pcm
        else:
            return None
        
        # This is Google's publicly known Chromium Speech API key.
        # It is NOT a private key - it has been publicly documented and used by
        # dozens of open-source projects (e.g. SpeechRecognition library on PyPI).
        # Source: https://chromium.googlesource.com/chromium/src/+/refs/heads/main/google_apis/google_api_keys.cc
        # We use it to avoid requiring users to create their own Google account or API key,
        # keeping the add-on 100% free and zero-setup for blind users.
        key = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
        url = f"https://www.google.com/speech-api/v2/recognize?output=json&client=chromium&lang={lang}&key={key}"
        
        req = urllib.request.Request(url, data=raw_16bit, headers={'Content-Type': f'audio/l16; rate={rate}'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_text = response.read().decode('utf-8')
                
            for line in res_text.split('\n'):
                if not line.strip():
                    continue
                try:
                    res = json.loads(line)
                    if "result" in res and len(res["result"]) > 0:
                        alts = res["result"][0].get("alternative", [])
                        if len(alts) > 0:
                            return alts[0].get("transcript", "")
                except:
                    pass
        except:
            pass
        return ""

    def _listen_and_process(self):
        try:
            wav_path = os.path.join(os.getenv("TEMP"), "suno_cmd.wav")
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except:
                    pass
                
            self.winmm.mciSendStringW("close all", None, 0, None)
            self.winmm.mciSendStringW("open new type waveaudio alias myrec", None, 0, None)
            
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            time.sleep(0.3)
            
            self.winmm.mciSendStringW("record myrec", None, 0, None)
            time.sleep(3.0)
            
            self.winmm.mciSendStringW("stop myrec", None, 0, None)
            self.winmm.mciSendStringW(f'save myrec "{wav_path}"', None, 0, None)
            self.winmm.mciSendStringW("close myrec", None, 0, None)
            
            core.callLater(10, ui.message, "Processing...")
            
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
                core.callLater(10, ui.message, "Failed to record audio. Microphone might be locked.")
                return
                
            with open(wav_path, "rb") as f:
                audio_data = f.read()
                
            text = self._recognize_google(audio_data, lang="en-US")
            if not text:
                text = self._recognize_google(audio_data, lang="ur-PK")
            
            if text:
                threading.Thread(target=self._process_command, args=(text,)).start()
            else:
                core.callLater(10, ui.message, "I couldn't hear any clear words.")
                
        except Exception as e:
            core.callLater(10, ui.message, f"Error: {str(e)}")
        finally:
            self.pause_wakeword = False
            try:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except:
                pass

    def script_toggleSleepMode(self, gesture):
        self.sleep_mode = not getattr(self, "sleep_mode", False)
        sleep_lock = os.path.join(os.getenv("TEMP"), "suno_sleep.lock")
        if self.sleep_mode:
            try:
                with open(sleep_lock, "w") as f:
                    f.write("1")
            except:
                pass
            ui.message("Suno AI Sleep Mode ON. Microphone is muted.")
        else:
            try:
                if os.path.exists(sleep_lock):
                    os.remove(sleep_lock)
            except:
                pass
            ui.message("Suno AI Sleep Mode OFF. Listening for wake word.")

    script_toggleSleepMode.__doc__ = "Toggles Suno AI Sleep Mode (Mutes wake word)."
    script_toggleSleepMode.category = "Suno AI"
    
    def restart_wakeword_process(self):
        if self.wakeword_process:
            try:
                self.wakeword_process.kill()
            except:
                pass

    def _run_wakeword_process(self):
        while self.keep_running:
            ww = config.conf["suno_ai"]["wake_word"]
            sens = config.conf["suno_ai"]["sensitivity"] / 100.0
            
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
            
            $choices = New-Object System.Speech.Recognition.Choices
            $choices.Add("{ww}")
            
            $wakeGrammarBuilder = New-Object System.Speech.Recognition.GrammarBuilder
            $wakeGrammarBuilder.Append($choices)
            $wakeGrammar = New-Object System.Speech.Recognition.Grammar($wakeGrammarBuilder)
            $dictationGrammar = New-Object System.Speech.Recognition.DictationGrammar
            
            try {{
                $recognizer.SetInputToDefaultAudioDevice()
            }} catch {{
                [Console]::WriteLine("MIC_ERROR")
                exit
            }}
            
            $recognizer.LoadGrammar($wakeGrammar)
            $recognizer.LoadGrammar($dictationGrammar)
            
            $global:WakeDetected = $false
            Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -Action {{
                if ($Event.SourceEventArgs.Result.Text -eq "{ww}" -and $Event.SourceEventArgs.Result.Confidence -gt {sens}) {{
                    $global:WakeDetected = $true
                }}
            }}
            
            $paused = $false
            $recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
            
            while ($true) {{
                if ($global:WakeDetected) {{
                    $global:WakeDetected = $false
                    [Console]::WriteLine("WAKE")
                }}
                
                $locked = (Test-Path "$env:TEMP\suno_pause.lock") -or (Test-Path "$env:TEMP\suno_sleep.lock")
                if ($locked -and -not $paused) {{
                    $recognizer.RecognizeAsyncCancel()
                    $paused = $true
                }}
                elseif (-not $locked -and $paused) {{
                    $recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)
                    $paused = $false
                }}
                Start-Sleep -Milliseconds 100
            }}
            '''
            ps_path = os.path.join(os.getenv("TEMP"), "suno_ai_wake.ps1")
            try:
                with open(ps_path, "w") as f:
                    f.write(ps_script)
            except:
                pass

            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.wakeword_process = subprocess.Popen(
                    ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    text=True
                )
                
                for line in iter(self.wakeword_process.stdout.readline, ''):
                    line = line.strip()
                    if line == "MIC_ERROR":
                        core.callLater(10, ui.message, "Suno AI Error: Microphone is disabled. Please allow access.")
                        time.sleep(10)
                        break
                    elif line == "WAKE":
                        self.script_startListening(None)
                
                if self.wakeword_process:
                    self.wakeword_process.kill()
                    self.wakeword_process = None
            except:
                time.sleep(2)

    def _process_command(self, user_text):
        try:
            reply = self._get_smart_reply(user_text.lower())
            core.callLater(10, ui.message, f"Suno AI: {reply}")
            if config.conf["suno_ai"].get("show_response_box", False):
                core.callLater(50, ui.browseableMessage, f"{reply}", "Suno AI Response")
        except Exception as e:
            core.callLater(10, ui.message, f"Error generating reply: {str(e)}")

    def _get_smart_reply(self, text):
        text = text.lower().strip()
        
        # 1. Custom Commands check
        for item in config.conf["suno_ai"]["custom_commands"]:
            if "=" in item:
                cmd, path = item.split("=", 1)
                cmd = cmd.strip().lower()
                if cmd and cmd in text:
                    path = path.strip()
                    os.system(f'start "" "{path}"')
                    return f"Executing {cmd}."
                    
        if "start voice translation" in text or "start translation" in text:
            self.start_voice_translation()
            return "Voice translation started. Please begin speaking."
            
        # 2. Parameterized Web Search
        query = ""
        platform = ""
        
        if text.startswith("google "):
            query = text.replace("google ", "", 1).strip()
            platform = "google"
        elif text.startswith("youtube "):
            query = text.replace("youtube ", "", 1).strip()
            platform = "youtube"
        else:
            search_match = re.search(r'(?:search|find|play)\s+(?:for\s+)?(.*?)\s+(?:on|in|from)\s+(youtube|google)', text)
            if search_match:
                query = search_match.group(1).strip()
                platform = search_match.group(2).strip()

        if query and platform:
            encoded = urllib.parse.quote(query)
            if platform == "youtube":
                os.system(f'start "" "https://www.youtube.com/results?search_query={encoded}"')
                return f"Searching for {query} on YouTube."
            elif platform == "google":
                os.system(f'start "" "https://www.google.com/search?q={encoded}"')
                return f"Searching for {query} on Google."
                
        # 2.5 Open Website
        web_match = re.search(r'(?:open website|go to|open)\s+([a-z0-9.-]+\.(?:com|org|net|pk|co|edu))', text.replace(" dot ", "."))
        if web_match:
            domain = web_match.group(1).strip()
            if not domain.startswith("http"):
                domain = "https://" + domain
            os.system(f'start "" "{domain}"')
            return f"Opening {domain}"
        if "time" in text or "waqt" in text:
            return "The time is " + datetime.datetime.now().strftime("%I:%M %p")
        elif "date" in text or "tareekh" in text:
            return "Today is " + datetime.datetime.now().strftime("%B %d, %Y")
        elif "weather" in text or "mausam" in text:
            try:
                req = urllib.request.Request("http://wttr.in/?format=3", headers={"User-Agent": "curl/7.68.0"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    return "The weather is: " + r.read().decode('utf-8').strip()
            except:
                return "I couldn't fetch the weather right now."
                
        math_str = text.replace("what is", "").replace("calculate", "").replace("tell me", "").strip()
        math_str = math_str.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("multiplied by", "*").replace("divided by", "/").replace("x", "*").replace("equals", "")
        math_clean = ''.join(c for c in math_str if c in "0123456789+-*/.()")
        
        if len(math_clean) > 2 and any(op in math_clean for op in "+-*/"):
            try:
                result = eval(math_clean)
                return f"The answer is {result}"
            except:
                pass
                
        # 3. System Management
        if "device info" in text or "system info" in text or "system management" in text:
            try:
                out = subprocess.check_output('powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption; Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"', shell=True).decode('utf-8', 'ignore').strip().split('\n')
                if len(out) >= 2:
                    return f"{out[0].strip()}. Processor: {out[1].strip()}."
            except:
                pass
            return "Could not fetch device info."
            
        if "storage info" in text or "storage management" in text:
            try:
                out = subprocess.check_output('powershell -Command "$d=Get-CimInstance Win32_LogicalDisk -Filter \\"DeviceID=\'C:\'\\"; \\"$([math]::Round($d.FreeSpace / 1GB)) GB free out of $([math]::Round($d.Size / 1GB)) GB\\""', shell=True).decode('utf-8', 'ignore').strip()
                return f"C Drive has {out}."
            except:
                return "Could not fetch storage info."
            
        if "ram info" in text or "ram management" in text:
            try:
                out = subprocess.check_output('powershell -Command "$o=Get-CimInstance Win32_OperatingSystem; \\"$([math]::Round($o.FreePhysicalMemory / 1024)) MB free out of $([math]::Round($o.TotalVisibleMemorySize / 1024)) MB total\\""', shell=True).decode('utf-8', 'ignore').strip()
                return f"RAM: {out}."
            except:
                return "Could not fetch RAM info."
                
        # 4. Screenshots and Camera
        if "take a screenshot" in text or "capture screen" in text:
            try:
                pics_dir = os.path.join(os.environ.get("USERPROFILE"), "Pictures")
                if not os.path.exists(pics_dir):
                    os.makedirs(pics_dir)
                filename = f"Screenshot_{int(time.time())}.png"
                filepath = os.path.join(pics_dir, filename)
                
                def do_screenshot():
                    try:
                        screen = wx.ScreenDC()
                        size = screen.GetSize()
                        bmp = wx.Bitmap(size.width, size.height)
                        mem = wx.MemoryDC(bmp)
                        mem.Blit(0, 0, size.width, size.height, screen, 0, 0)
                        del mem
                        bmp.SaveFile(filepath, wx.BITMAP_TYPE_PNG)
                    except:
                        pass
                
                # Screenshot must be taken in the main thread
                core.callLater(10, do_screenshot)
                return "Taking screenshot. It will be saved in your Pictures folder in a moment."
            except Exception as e:
                return "Failed to take screenshot."
                
        if "take a picture" in text or "capture photo" in text:
            try:
                # avicap32 fails on modern 64-bit systems with multiple virtual cameras.
                # The most accessible and reliable way is to launch the native Windows Camera app.
                os.system("start microsoft.windows.camera:")
                
                if "description" in text or "recognize" in text:
                    return "Camera app opened. Press Enter or Space to take a picture. Image description AI requires an API key which is not configured."
                return "Camera app opened. Press Enter or Space to take a picture. It will be saved in your Camera Roll."
            except Exception as e:
                return "Failed to access camera app."
                
        # 5. Open ANY App (Start Menu Fuzzy Search & Fallback)
        if "open" in text or "launch" in text or "start" in text or "kholo" in text:
            match = re.search(r'(open|launch|start|kholo)\s+(.*)', text)
            if match:
                app_name = match.group(2).strip()
            else:
                app_name = text.replace("kholo", "").strip()
                
            # Quick hardcoded fallbacks
            apps = {
                "chrome": "chrome", "notepad": "notepad", "calculator": "calc",
                "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
                "whatsapp": "whatsapp:", "browser": "microsoft-edge:", "edge": "msedge"
            }
            for key in apps:
                if key == app_name:
                    os.system(f"start {apps[key]}")
                    return f"Opening {app_name}."
            
            # Start Menu Search
            import glob
            dirs = [
                os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
            ]
            for d in dirs:
                if not os.path.exists(d): continue
                for path in glob.glob(d + "\\**\\*.lnk", recursive=True):
                    filename = os.path.basename(path).lower()
                    if app_name in filename:
                        os.system(f'start "" "{path}"')
                        return f"Opening {app_name}."
                        
            # Final fallback
            try:
                os.system(f"start {app_name}")
                return f"Attempting to open {app_name}."
            except:
                return f"Failed to open {app_name}."
                
        if "stop" in text or "exit" in text or "shut up" in text:
            return "Goodbye."
            
        query = text.replace("who is", "").replace("what is", "").replace("tell me about", "").replace("search for", "").strip()
        if not query:
            return "I am Suno AI. How can I help you?"
            
        try:
            encoded_query = urllib.parse.quote(query)
            
            try:
                ddg_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json"
                req_ddg = urllib.request.Request(ddg_url, headers={"User-Agent": "SunoAI/1.9.1"})
                with urllib.request.urlopen(req_ddg, timeout=3) as ddg_resp:
                    ddg_data = json.loads(ddg_resp.read().decode("utf-8"))
                    if ddg_data.get("AbstractText"):
                        return ddg_data["AbstractText"]
            except:
                pass
            
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&utf8=&format=json"
            req = urllib.request.Request(search_url, headers={"User-Agent": "SunoAI/1.9.1"})
            
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
                search_results = data.get("query", {}).get("search", [])
                
                if not search_results:
                    return "I couldn't find information on that."
                    
                best_title = search_results[0]["title"]
            
            encoded_title = urllib.parse.quote(best_title)
            extract_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exsentences=3&exlimit=1&titles={encoded_title}&explaintext=1&format=json&redirects=1"
            req2 = urllib.request.Request(extract_url, headers={"User-Agent": "SunoAI/1.9.1"})
            
            with urllib.request.urlopen(req2, timeout=4) as response2:
                data2 = json.loads(response2.read().decode("utf-8"))
                pages = data2["query"]["pages"]
                for page_id in pages:
                    if page_id == "-1":
                        return f"I found {best_title} but couldn't get the details."
                    else:
                        extract = pages[page_id].get("extract", "")
                        extract = re.sub(r'\(.*?\)', '', extract)
                        return extract if extract else f"No summary available for {best_title}."
                        
        except Exception as e:
            return f"I'm having trouble connecting to Wikipedia right now. Details: {str(e)}"
