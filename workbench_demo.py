"""Export a complete saved workbench record with scripted corrections."""

import json

from correction_demo import DEMO_ENTRIES
from workbench import apply_command, start_record


def build_record():
    record = start_record(
        {'name': 'Scripted parameterized correction', 'entries': list(DEMO_ENTRIES)},
        'force_cart_0',
        'Scripted demonstration: mass 2 kg and acceleration 5 m/s^2. '
        'The 12 N mistake and 10 N correction are supplied responses; all claims are unchecked.',
    )
    commands = [
        {'operation': 'expand', 'frame_id': 'F', 'position': 0, 'entry_index': 0},
        {'operation': 'inject', 'frame_id': 'F/0', 'position': 0, 'response': '2 kg'},
        {'operation': 'inject', 'frame_id': 'F/0', 'position': 1, 'response': '5 m/s^2'},
        {'operation': 'reduce', 'frame_id': 'F/0', 'response': '12 N', 'note': 'scripted arithmetic mistake'},
        {'operation': 'reduce', 'frame_id': 'F', 'response': 'Prediction: 12 N'},
        {'operation': 'reopen', 'frame_id': 'F/0', 'note': 'reopen the original product'},
        {'operation': 'reduce', 'frame_id': 'F/0', 'response': '10 N', 'note': 'scripted correction'},
        {'operation': 'reduce', 'frame_id': 'F', 'response': 'Prediction: 10 N'},
    ]
    for command in commands:
        record = apply_command(record, command)
    return record


if __name__ == '__main__':
    print(json.dumps(build_record(), ensure_ascii=False, indent=2))
