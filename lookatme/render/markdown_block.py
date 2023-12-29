"""
Defines render functions that render lexed markdown block tokens into urwid
representations
"""


import pygments.styles
import urwid

from lookatme.contrib import contrib_first
from lookatme.tutorial import tutor


@tutor(
    "markdown",
    "tables",
    r"""
    Rows in tables are defined by separating columns with `|` characters. The
    header row is the first row defined and is separated by hypens (`---`).

    Alignment within a column can be set by adding a colon, `:`, to the left,
    right, or both ends of a header's separator.

    <TUTOR:EXAMPLE>
    | left align | centered | right align |
    |------------|:--------:|------------:|
    | 1          |     a    |           A |
    | 11         |    aa    |          AA |
    | 111        |    aaa   |         AAA |
    | 1111       |   aaaaa  |        AAAA |
    </TUTOR:EXAMPLE>

    ## Style

    Tables can be styled with slide metadata. This is the default style:

    <TUTOR:STYLE>table</TUTOR:STYLE>
    """,
)
@contrib_first
def render_table(token, body, stack, loop):
    """Renders a table using the :any:`Table` widget.

    See :any:`lookatme.tui.SlideRenderer.do_render` for argument and return
    value descriptions.

    The table widget makes use of the styles below:

    .. code-block:: yaml

        table:
          column_spacing: 3
          header_divider: "─"

    :returns: A list of urwid Widgets or a single urwid Widget
    """
    from lookatme.widgets.table import Table

    headers = token["header"]
    aligns = token["align"]
    cells = token["cells"]

    table = Table(cells, headers=headers, aligns=aligns)
    padding = urwid.Padding(table, width=table.total_width + 2, align="center")

    def table_changed(*args, **kwargs):
        padding.width = table.total_width + 2

    urwid.connect_signal(table, "change", table_changed)

    return padding
