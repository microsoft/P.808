from pathlib import Path

import pytest


TEMPLATE_DIRECTORY = Path(__file__).parents[1] / "src" / "P808Template"
PARALLEL_SESSION_TEMPLATES = [
    "ACR_template.html",
    "bw_check.html",
    "echo_impairment_test_fest_template.html",
    "echo_impairment_test_template.html",
    "P808_multi.html",
    "P831_ACR_template.html",
    "P835_personalized_template3.html",
    "P835_template_one_audio.html",
    "P835_template.html",
]


@pytest.mark.parametrize("template_name", PARALLEL_SESSION_TEMPLATES)
def test_parallel_session_identifier_uses_web_crypto(template_name):
    """
    Verify that browser-session identifiers use cryptographic randomness.

    :param template_name: HTML template containing parallel-session detection.
    :return: None.
    """
    template = (TEMPLATE_DIRECTORY / template_name).read_text(encoding="utf-8")
    function_start = template.index("function initializeActivePageMonitoring")
    function_end = template.index("document.addEventListener", function_start)
    monitoring_setup = template[function_start:function_end]

    assert "Math.random()" not in monitoring_setup
    assert "new Uint32Array(4)" in monitoring_setup
    assert "window.crypto.getRandomValues(randomValues);" in monitoring_setup
    assert 'sessionId = randomValues.join("-");' in monitoring_setup


def test_all_parallel_session_templates_have_security_coverage():
    """
    Verify that every template using the session cookie is covered by the security test.

    :return: None.
    """
    templates_with_session_cookie = {
        path.name
        for path in TEMPLATE_DIRECTORY.glob("*.html")
        if "sessionIdVariableName" in path.read_text(encoding="utf-8")
    }

    assert templates_with_session_cookie == set(PARALLEL_SESSION_TEMPLATES)
