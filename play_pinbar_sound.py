from playsound import playsound
from gtts import gTTS
import json

import os


class PinbarSoundPlayer:
    def __init__(self, cache_file='data/sound_cache.json'):
        self.cache_file = cache_file
        self.cache = self.load_cache()

    def load_cache(self):
        # 从 JSON 文件加载缓存
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_cache(self):
        # 将缓存保存到 JSON 文件
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=4)

    def play_sound(self, text):
        # 将文本中的特殊字符替换为下划线以生成有效的文件名
        safe_text = ''.join(e if e.isalnum() or e == '_' else '_' for e in text)

        # 检查缓存中是否已有该文本的 MP3
        if text in self.cache:
            mp3_file = self.cache[text]
        else:
            # 生成新的 MP3 文件
            tts = gTTS(text=text, lang='zh')
            mp3_file = f"data/{safe_text}.mp3"
            tts.save(mp3_file)
            self.cache[text] = mp3_file
            self.save_cache()  # 更新缓存

        # 使用绝对路径来播放文件
        mp3_file_path = os.path.abspath(mp3_file)

        # 确保路径中没有多余的引号
        mp3_file_path = f'"{mp3_file_path}"'

        # 播放 MP3 文件
        playsound(mp3_file_path)  # 使用playsound库进行跨平台播放

# 示例用法
# player = PinbarSoundPlayer()
# player.play_sound("好消息，好消息 ，A U 15 分钟级别的 pinbar 来了！赶紧看看吧！")
