from typer.testing import CliRunner

from trapper_browser.main import app

runner = CliRunner()

def test_app():
    result = runner.invoke(app, [])
    print(result.output)
    assert result.exit_code == 2
    assert "Missing command" in result.output

def test_show_config():
    result = runner.invoke(app, ["show-config"])
    print(result.output)
    assert result.exit_code == 0
    assert "Configuration" in result.output

def test_set_config():
    result = runner.invoke(app, ["set-config", "trapper_url", "http://example.com"])
    print(result.output)
    assert result.exit_code == 0

    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0
    assert "http://example.com" in result.output


