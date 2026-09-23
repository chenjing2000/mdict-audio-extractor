from mdict_audio_extractor.app import extract_wordlist_audio


if __name__ == "__main__":
    WORDLIST_PATH = r"E:\pywork\ielts\vocabulary\IELTS_Band7_WordList.json"

    MDX_PATH = (
        r"D:\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdx"
    )

    MDD_PATH = (
        r"D:\Softs\Dictionaries\牛津英汉双解词典第10版（淘宝）"
        r"\牛津高阶（第10版 英汉双解） V14_3.mdd"
    )

    extract_wordlist_audio(
        WORDLIST_PATH,
        MDX_PATH,
        MDD_PATH,
    )
