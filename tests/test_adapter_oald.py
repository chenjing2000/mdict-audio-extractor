from mdict_audio_extractor.adapter_oald import parse_headword_pronunciations


def test_extracts_headword_uk_us_and_ignores_sentence_audio():
    html = """
    <div class="entry" id="apple">
      <div class="top-container">
        <div class="top-g">
          <div class="webtop">
            <h1 class="headword">apple</h1>
            <span class="phonetics">
              <div class="phons_br" geo="br">
                <a href="sound://apple__gb_5.mp3"
                   class="sound audio_play_button pron-uk icon-audio"></a>
                <span class="phon">/ˈæpl/</span>
              </div>
              <div class="phons_n_am" geo="n_am">
                <a href="sound://apple__us_1.mp3"
                   class="sound audio_play_button pron-us icon-audio"></a>
                <span class="phon">/ˈæpl/</span>
              </div>
            </span>
          </div>
        </div>
      </div>

      <audio-wr>
        <a href="sound://_apple__gbs_2.mp3"
           class="sound audio_play_button pron-uk icon-audio"></a>
        <a href="sound://_apple__uss_2.mp3"
           class="sound audio_play_button pron-us icon-audio"></a>
      </audio-wr>
    </div>
    """

    values = parse_headword_pronunciations(html)

    assert [(x.accent, x.resource, x.ipa) for x in values] == [
        ("uk", "apple__gb_5.mp3", "/ˈæpl/"),
        ("us", "apple__us_1.mp3", "/ˈæpl/"),
    ]


def test_ubiquitous_pattern():
    html = """
    <div class="entry" id="ubiquitous">
      <div class="webtop">
        <h1 class="headword">ubiquitous</h1>
        <span class="phonetics">
          <div class="phons_br" geo="br">
            <a href="sound://ubiquitous__gb_1.mp3" class="pron-uk"></a>
            <span class="phon">/juːˈbɪkwɪtəs/</span>
          </div>
          <div class="phons_n_am" geo="n_am">
            <a href="sound://ubiquitous__us_1.mp3" class="pron-us"></a>
            <span class="phon">/juːˈbɪkwɪtəs/</span>
          </div>
        </span>
      </div>
    </div>
    """

    values = parse_headword_pronunciations(html)

    assert [x.resource for x in values] == [
        "ubiquitous__gb_1.mp3",
        "ubiquitous__us_1.mp3",
    ]
