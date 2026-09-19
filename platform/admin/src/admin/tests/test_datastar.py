from admin.datastar import patch_elements, patch_signals


def test_patch_signals_wire_format():
    out = patch_signals({'a': 1, 'b': 'x'})
    assert out.startswith('event: datastar-patch-signals\n')
    assert 'data: signals {"a": 1, "b": "x"}' in out
    assert out.endswith('\n\n')


def test_patch_elements_wire_format():
    out = patch_elements('<div id="x">hi</div>')
    lines = out.splitlines()
    assert lines[0] == 'event: datastar-patch-elements'
    assert lines[1] == 'data: elements <div id="x">hi</div>'
    assert out.endswith('\n\n')


def test_patch_elements_with_selector_and_mode():
    out = patch_elements('<div>x</div>', selector='#target', mode='append')
    lines = out.splitlines()
    assert 'data: selector #target' in lines
    assert 'data: mode append' in lines


def test_patch_elements_multiline_html():
    out = patch_elements('<div>\n  <span>x</span>\n</div>')
    prefix = 'data: elements'
    element_lines = [line for line in out.splitlines() if line.startswith(prefix)]
    assert len(element_lines) == 3
