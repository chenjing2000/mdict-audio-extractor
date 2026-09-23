from mdict_audio_extractor.app import mdict_audio_extractor
from mdict_audio_extractor.example_audio import example_audio_synthesis


if __name__ == "__main__":
    WORDLIST_PATH = r"C:\pywork\ielts\vocabulary\IELTS_Band7_WordList.json"

    MDX_PATH = (
        r"C:\MyDocs\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdx"
    )

    MDD_PATH = (
        r"C:\MyDocs\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdd"
    )

    mdict_audio_extractor(
        WORDLIST_PATH,
        MDX_PATH,
        MDD_PATH,
    )

    # UK voice 可选：
    #   en-GB-SoniaNeural   女声，默认
    #   en-GB-LibbyNeural   女声
    #   en-GB-RyanNeural    男声
    #
    # US voice 可选：
    #   en-US-JennyNeural   女声，默认
    #   en-US-AriaNeural    女声
    #   en-US-GuyNeural     男声
    #
    # wait_seconds 只在 TTS 第一次失败后、第二次重试前等待；默认 2 秒。
    example_audio_synthesis(
        WORDLIST_PATH,
        # uk_voice="en-GB-SoniaNeural",
        # us_voice="en-US-JennyNeural",
        # wait_seconds=2,
    )
