import textwrap

import PySimpleGUI as sg


def error_popup(error_msg: str) -> None:
    """Run error modal window.

    Args:
        error_msg: Error message.
    """

    # Adjust error message width
    error_msg = '\n'.join(
        textwrap.wrap(error_msg, width=60, replace_whitespace=False, break_on_hyphens=False)
    )

    # Window layout
    layout = [
        [
            sg.Text(error_msg),
        ],
        [
            sg.Column([
                [
                    sg.Button('Close', key='-BTN_CLOSE-', size=(8, 1), button_color='firebrick3',
                              focus=True, bind_return_key=True, pad=((0, 0), 3)),
                ],
            ], expand_x=True, element_justification='center'),
        ],
    ]

    window = sg.Window('Error', layout, auto_size_text=True, finalize=True,
                       font='Any 12', modal=True, keep_on_top=True)

    while True:
        event, _ = window.Read()

        # Close window
        if event in (None, '-BTN_CLOSE-'):
            break

    window.close()
