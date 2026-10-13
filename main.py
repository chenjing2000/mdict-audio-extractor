from audio_extractor.app import audio_extractor


if __name__ == "__main__":
    WORDLIST_PATH = r"C:\Projects\wordlists\wordlist 01 education and learning.json"

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
        # uk_voice="en-GB-SoniaNeural",
        # us_voice="en-US-JennyNeural",
        # wait_seconds=2,
    )
