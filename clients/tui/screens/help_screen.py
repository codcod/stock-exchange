from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Markdown

_HELP_TEXT = """# Exchange Terminal — Key Bindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `b` | Focus order entry, set side to BUY |
| `s` | Focus order entry, set side to SELL |
| `d` | Cancel selected open order |
| `Enter` | Select ticker in Market Watch |
| `1` | Switch to Main tab |
| `2` | Switch to Order History tab |
| `Ctrl+R` | Force data refresh |
| `F1` | Show this help |
| `Escape` | Close this dialog |

## Order Entry Tips

- Select MARKET to skip the price field
- Notional value updates live as you type
- Orders are validated before submission
- Rejection reasons appear in the title bar
"""


class HelpScreen(ModalScreen):
    BINDINGS = [Binding('escape', 'dismiss', 'Close')]

    def compose(self) -> ComposeResult:
        yield Markdown(_HELP_TEXT, id='help-dialog')
