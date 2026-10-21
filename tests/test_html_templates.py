from pathlib import Path


def test_p835_unanswered_questions_link_closes_before_paragraph():
    """
    Verify that the P.835 unanswered-questions link has a closing anchor tag.

    :return: None.
    """
    template_path = (
        Path(__file__).parents[1]
        / "src"
        / "P808Template"
        / "P835_template_one_audio.html"
    )
    template = template_path.read_text(encoding="utf-8")
    link_start = template.index('<a id="myLink"')
    link_end = template.index("</a>", link_start)
    paragraph_end = template.index("</p>", link_start)

    assert link_end < paragraph_end
