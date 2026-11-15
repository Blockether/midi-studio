import base64
import json

from studio.aws import handler


def call(path, method="GET"):
    """Send one function URL event to the handler."""
    return handler({"rawPath": path, "requestContext": {"http": {"method": method}}})


def test_a_text_answer_goes_out_as_text():
    answer = call("/api/songs")
    assert (answer["statusCode"], answer["isBase64Encoded"]) == (200, False)
    assert json.loads(answer["body"])[0]["id"]


def test_a_midi_file_goes_out_as_base64():
    answer = call("/songs/night-drive.mid")
    assert (answer["statusCode"], answer["isBase64Encoded"]) == (200, True)
    assert base64.b64decode(answer["body"])[:4] == b"MThd"


def test_the_handler_passes_the_method_and_the_status():
    assert call("/", "POST")["statusCode"] == 405
    assert call("/api/songs/none")["statusCode"] == 404
