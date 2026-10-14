from audio_extractor.app import audio_extractor


if __name__ == "__main__":
    WORDLIST_PATH = r"C:\MyDocs\magazines\The Economist\2026-09-26\020 Split decision"

    MDX_PATH = (
        r"C:\MyDocs\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdx"
    )

    MDD_PATH = (
        r"C:\MyDocs\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdd"
    )

    audio_extractor(
        WORDLIST_PATH,
        MDX_PATH,
        MDD_PATH,
        tts_enabled=True,  # 默认关闭；开启后生成例句/片段音频
        # uk_voice="en-GB-SoniaNeural",
        # us_voice="en-US-JennyNeural",
        # wait_seconds=2,
    )
