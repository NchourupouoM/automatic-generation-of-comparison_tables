from app.services.orchestrator import _locate_segment_boundaries


def test_boundaries_are_monotonic_and_correct():
    md = "Intro blurb. Paper Alpha about foxes. filler filler Paper Beta about bees. tail"
    offsets = _locate_segment_boundaries(md, ["Paper Alpha", "Paper Beta"])
    assert offsets[0] == md.index("Paper Alpha")
    assert offsets[1] == md.index("Paper Beta")
    assert offsets[0] < offsets[1]


def test_each_paper_gets_distinct_slice():
    md = "AAA Paper Alpha content-alpha BBB Paper Beta content-beta CCC"
    offsets = _locate_segment_boundaries(md, ["Paper Alpha", "Paper Beta"])
    seg_alpha = md[offsets[0]:offsets[1]]
    seg_beta = md[offsets[1]:]
    assert "content-alpha" in seg_alpha and "content-beta" not in seg_alpha
    assert "content-beta" in seg_beta


def test_unlocatable_title_falls_back_without_crashing():
    md = "Only Paper Alpha exists here."
    offsets = _locate_segment_boundaries(md, ["Paper Alpha", "Nonexistent Paper Zeta"])
    assert len(offsets) == 2
    # The missing title inherits the previous boundary (monotonic, no negative index).
    assert offsets[1] >= offsets[0] >= 0


def test_repeated_titles_advance_search():
    md = "Header Paper Alpha one. Later Paper Alpha two."
    offsets = _locate_segment_boundaries(md, ["Paper Alpha", "Paper Alpha"])
    assert offsets[1] > offsets[0]
