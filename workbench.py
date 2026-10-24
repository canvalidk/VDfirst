"""Bounded, replayable VDfirst records for a human-operated workbench.

This protocol does not evaluate responses or certify their meanings. Its
digests and replay checks establish record consistency, not authorship.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID, uuid4

from demand import (
    Demand, ExpandProvenance, ExpandResolution, InjectProvenance,
    InjectResolution, RecallResolution, Trace,
)
from engine import VDInstance
from prediction_set import build_prediction_set
from simulator import Simulator

MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_COMMANDS = 80
MAX_ENTRIES = 64
MAX_TEXT = 4096
MAX_FRAMES = 96
MAX_DEPTH = 24
MAX_HOLES = 32
SOURCE_FILES = (
    'application.py', 'definiens.py', 'demand.py', 'engine.py',
    'prediction_set.py', 'residual.py', 'simulator.py', 'workbench.py',
)


class RecordError(ValueError):
    """An invalid, inconsistent or unsupported workbench record/command."""


def _canonical(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise RecordError('record must contain finite, UTF-8 JSON values') from exc


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _detached(value):
    data = _canonical(value)
    if len(data) > MAX_RECORD_BYTES:
        raise RecordError('record exceeds the 8 MiB size limit')
    return json.loads(data)


def _source_producer() -> dict:
    """Fingerprint explicit protocol sources, independent of checkout CRLF."""
    digest = hashlib.sha256()
    for filename in SOURCE_FILES:
        content = Path(__file__).with_name(filename).read_bytes().replace(b'\r\n', b'\n')
        for part in (filename.encode('utf-8'), content):
            digest.update(len(part).to_bytes(8, 'big'))
            digest.update(part)
    return {'name': 'VDfirst', 'protocol_version': 1, 'engine_sha256': digest.hexdigest()}


_PRODUCER = _source_producer()


def producer() -> dict:
    """Identity of the loaded engine; restart the bridge after source edits."""
    return dict(_PRODUCER)


def _keys(value, required, optional=(), label='object'):
    if type(value) is not dict or not set(required) <= value.keys():
        raise RecordError(f'{label} is missing required fields')
    if set(value) - set(required) - set(optional):
        raise RecordError(f'{label} has unsupported fields')


def _text(value, label, *, empty=False, maximum=MAX_TEXT):
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        raise RecordError(f'{label} must be {"a" if empty else "a nonempty"} string of at most {maximum} characters')
    _canonical(value)
    return value


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise RecordError(f'{label} must be a nonnegative integer')
    return value


def _dictionary(value):
    _keys(value, ('name', 'entries'), label='dictionary')
    name = _text(value['name'], 'dictionary name', maximum=256)
    entries = value['entries']
    if type(entries) is not list or len(entries) > MAX_ENTRIES:
        raise RecordError(f'dictionary entries must be an array of at most {MAX_ENTRIES} pairs')
    pairs = []
    for entry in entries:
        if type(entry) not in (list, tuple) or len(entry) != 2:
            raise RecordError('each dictionary entry must be a headword/definition pair')
        pairs.append((_text(entry[0], 'headword', maximum=256),
                      _text(entry[1], 'definition', empty=True)))
    if sum(len(a) + len(b) for a, b in pairs) > 65536:
        raise RecordError('dictionary text exceeds the 64 Ki character limit')
    instance = VDInstance(name)
    try:
        instance.append_many(pairs)
    except (ValueError, TypeError, IndexError, RecursionError) as exc:
        raise RecordError(f'invalid dictionary: {exc}') from exc
    result = {'name': name, 'entries': [
        {'index': i, 'headword': headword, 'definition': definition}
        for i, (headword, definition) in enumerate(pairs)
    ]}
    result['sha256'] = _digest(result)
    return result, Simulator(instance)


def _frame_id(address):
    return 'F' + ''.join(f'/{position}' for position in address)


def _members(trace):
    out = []

    def walk(node, address):
        if len(address) > MAX_DEPTH or len(out) >= MAX_FRAMES:
            raise RecordError('trace exceeds frame/depth limits')
        if node.definiens.order > MAX_HOLES:
            raise RecordError(f'a frame may contain at most {MAX_HOLES} holes')
        out.append((node, address))
        for position, child in sorted(node.children().items()):
            walk(child, (*address, position))

    walk(trace.root, ())
    return out


def _snapshot(trace, sim, command_index, title):
    frames = []
    prediction_set = build_prediction_set(trace).to_dict()
    used = len(_canonical(prediction_set)) + 512

    def budget(value):
        nonlocal used
        used += len(_canonical(value)) + 2
        if used > MAX_RECORD_BYTES:
            raise RecordError('generated snapshot exceeds the record size limit')

    for node, address in _members(trace):
        render = node.text()
        if len(render) > MAX_TEXT * 4:
            raise RecordError('rendered frame exceeds the text limit')
        holes = []
        for position, headword in enumerate(node.definiens.headwords):
            resolution = node.resolutions.get(position)
            kind = ('expand' if isinstance(resolution, ExpandResolution)
                    else 'recall' if isinstance(resolution, RecallResolution)
                    else 'inject' if isinstance(resolution, InjectResolution) else None)
            candidates = []
            if resolution is None:
                for index in sim.entry_indexes(headword):
                    instantiated = sim.instantiated_entry_text(index, headword)
                    if len(instantiated) > MAX_TEXT * 4:
                        raise RecordError('instantiated definition exceeds the text limit')
                    candidate = {
                        'entry_index': index, 'headword': sim.entry_headword(index),
                        'definition': sim.entry_text(index),
                        'instantiated_definition': instantiated,
                    }
                    budget(candidate)
                    candidates.append(candidate)
            hole = {
                'position': position, 'headword': headword, 'resolution': kind,
                'child_frame_id': _frame_id((*address, position))
                if isinstance(resolution, (ExpandResolution, InjectResolution)) else None,
                'source_index': getattr(resolution, 'source_index', None),
                'candidates': candidates,
            }
            budget({key: value for key, value in hole.items() if key != 'candidates'})
            holes.append(hole)
        frame = {
            'id': _frame_id(address), 'address': list(address),
            'parent_id': _frame_id(address[:-1]) if address else None,
            'via_position': address[-1] if address else None,
            'render': render, 'resolved': node.is_resolved, 'reduced': node.reduced,
            'source_index': getattr(node.provenance, 'source_index', None),
            'headwords': list(node.definiens.headwords),
            'latents': list(node.definiens.residual.latent), 'holes': holes,
        }
        budget({key: value for key, value in frame.items() if key != 'holes'})
        frames.append(frame)
    return {'id': f'S{command_index + 1}', 'command_index': command_index,
            'title': title, 'root_frame_id': 'F', 'event_count': len(trace.events),
            'frames': frames, 'prediction_set': prediction_set}


def _command(value):
    _keys(value, ('operation', 'frame_id'),
          ('position', 'entry_index', 'response', 'latents', 'note'), 'command')
    operation = value['operation']
    if type(operation) is not str or operation not in {'expand', 'recall', 'inject', 'reduce', 'reopen', 'clean'}:
        raise RecordError('unsupported command operation')
    _text(value['frame_id'], 'frame ID', maximum=128)
    if not re.fullmatch(r'F(?:/(?:0|[1-9][0-9]*))*', value['frame_id']):
        raise RecordError('invalid frame ID')
    if 'note' in value:
        _text(value['note'], 'command note', empty=True, maximum=1024)
    extras = {'expand': {'position', 'entry_index'}, 'recall': {'position', 'entry_index'},
              'inject': {'position', 'response'}, 'reduce': {'response'},
              'reopen': set(), 'clean': {'latents'}}[operation]
    if set(value) - {'operation', 'frame_id', 'note'} != extras:
        raise RecordError(f'{operation} requires exactly {", ".join(sorted(extras)) or "no extra fields"}')
    for field in ('position', 'entry_index'):
        if field in extras:
            _integer(value[field], field)
    if 'response' in extras:
        _text(value['response'], 'response')
    if 'latents' in extras:
        if type(value['latents']) is not list or len(value['latents']) > MAX_HOLES + 1:
            raise RecordError('latents must be a bounded string array')
        for latent in value['latents']:
            _text(latent, 'latent', empty=True)
    return _detached(value)


def _execute(trace, sim, command):
    operation, frame_id = command['operation'], command['frame_id']
    node = next((node for node, address in _members(trace) if _frame_id(address) == frame_id), None)
    if node is None:
        raise RecordError(f'unknown frame {frame_id}')
    note = command.get('note', '')
    detail = f'{operation} at {frame_id}' + (f': {note}' if note else '')
    position = command.get('position')
    if operation in ('expand', 'recall', 'inject'):
        node._check_open_position(position)
    if operation in ('expand', 'recall'):
        index = command['entry_index']
        headword = node.headword_at(position)
        if index not in sim.entry_indexes(headword):
            raise RecordError(f'E{index} is not a candidate for {headword}')
        text = sim.instantiated_entry_text(index, headword)
        if len(text) > MAX_TEXT * 4:
            raise RecordError('instantiated definition exceeds the text limit')
        if operation == 'expand':
            child = Demand(sim.analyse(text), provenance=ExpandProvenance(index))
            node.resolve_expand(position, child, index)
        else:
            node.resolve_recall(position, text, index)
        trace.record_event(operation, f'{detail}; position {position}; E{index}')
    elif operation == 'inject':
        text = command['response']
        child = Demand(sim.analyse(text), provenance=InjectProvenance(text))
        trace.inject_node(node, position, child, text, f'{detail}; position {position}')
    elif operation == 'reduce':
        trace.reduce_node(node, command['response'], detail)
    elif operation == 'reopen':
        trace.unreduce_node(node, detail)
    else:
        trace.clean_node(node, command['latents'], detail)
    return f'{operation.capitalize()} · {frame_id}'


def _events(trace):
    return [dict(asdict(event), id=f'event-{index}', index=index)
            for index, event in enumerate(trace.events)]


def _seal(record):
    record['sha256'] = _digest({key: value for key, value in record.items() if key != 'sha256'})
    return _detached(record)


def start_record(dictionary, demand, context='') -> dict:
    """Start from the exact supplied dictionary, demand and question context."""
    demand = _text(demand, 'starting demand')
    context = _text(context, 'question context', empty=True, maximum=8192)
    dictionary, sim = _dictionary(dictionary)
    try:
        trace = Trace.start(sim, demand)
        snapshot = _snapshot(trace, sim, -1, 'Trace started')
    except (ValueError, TypeError, IndexError, RecursionError) as exc:
        raise RecordError(str(exc)) from exc
    return _seal({'format': 'vd-trace-record', 'version': 1,
                  'record_id': str(uuid4()), 'producer': producer(),
                  'dictionary': dictionary, 'question': {'demand': demand, 'context': context},
                  'commands': [], 'events': _events(trace), 'snapshots': [snapshot]})


def _replay(record):
    record = _detached(record)
    _keys(record, ('format', 'version', 'record_id', 'sha256', 'producer', 'dictionary',
                   'question', 'commands', 'events', 'snapshots'), label='record')
    if record['format'] != 'vd-trace-record' or type(record['version']) is not int or record['version'] != 1:
        raise RecordError('unsupported record format/version')
    try:
        if type(record['record_id']) is not str or str(UUID(record['record_id'])) != record['record_id']:
            raise ValueError()
    except (ValueError, AttributeError, TypeError) as exc:
        raise RecordError('invalid record ID') from exc
    if record['sha256'] != _digest({key: value for key, value in record.items() if key != 'sha256'}):
        raise RecordError('record digest mismatch')
    if _canonical(record['producer']) != _canonical(producer()):
        raise RecordError('unsupported engine fingerprint; saved playback remains available')
    _keys(record['dictionary'], ('name', 'entries', 'sha256'), label='saved dictionary')
    saved_entries = record['dictionary']['entries']
    if type(saved_entries) is not list or len(saved_entries) > MAX_ENTRIES:
        raise RecordError('invalid saved dictionary entries')
    pairs = []
    for index, entry in enumerate(saved_entries):
        _keys(entry, ('index', 'headword', 'definition'), label='saved dictionary entry')
        if type(entry['index']) is not int or entry['index'] != index:
            raise RecordError('dictionary entry indexes must be consecutive')
        pairs.append([entry['headword'], entry['definition']])
    dictionary, sim = _dictionary({'name': record['dictionary']['name'], 'entries': pairs})
    if _canonical(dictionary) != _canonical(record['dictionary']):
        raise RecordError('dictionary digest mismatch')
    _keys(record['question'], ('demand', 'context'), label='question')
    _text(record['question']['demand'], 'starting demand')
    _text(record['question']['context'], 'question context', empty=True, maximum=8192)
    if type(record['commands']) is not list or len(record['commands']) > MAX_COMMANDS:
        raise RecordError(f'a record may contain at most {MAX_COMMANDS} commands')
    if (type(record['snapshots']) is not list or len(record['snapshots']) != len(record['commands']) + 1
            or type(record['events']) is not list or len(record['events']) != len(record['commands']) + 1):
        raise RecordError('record must contain one snapshot and event per operation, plus bootstrap')
    trace = Trace.start(sim, record['question']['demand'])
    snapshots = [_snapshot(trace, sim, -1, 'Trace started')]
    metadata_bytes = len(_canonical({key: value for key, value in record.items() if key not in ('snapshots', 'events')}))
    snapshot_bytes = len(_canonical(snapshots[0])) + 2
    for index, command in enumerate(record['commands']):
        title = _execute(trace, sim, _command(command))
        snapshot = _snapshot(trace, sim, index, title)
        snapshot_bytes += len(_canonical(snapshot)) + 2
        if metadata_bytes + snapshot_bytes + len(_canonical(_events(trace))) + 128 > MAX_RECORD_BYTES:
            raise RecordError('generated history exceeds the record size limit')
        snapshots.append(snapshot)
    if _canonical(record['events']) != _canonical(_events(trace)):
        raise RecordError('recorded events do not match command replay')
    if _canonical(record['snapshots']) != _canonical(snapshots):
        raise RecordError('recorded snapshots do not match command replay')
    return record, trace, sim


def validate_record(record) -> dict:
    """Replay and check consistency; never mark scientific claims verified."""
    try:
        return _replay(record)[0]
    except RecordError:
        raise
    except (ValueError, TypeError, IndexError, KeyError, RecursionError) as exc:
        raise RecordError(f'invalid recorded operation: {exc}') from exc


def apply_command(record, command) -> dict:
    """Append one valid operation after replay; preserve every earlier snapshot."""
    try:
        result, trace, sim = _replay(record)
        if len(result['commands']) >= MAX_COMMANDS:
            raise RecordError(f'a record may contain at most {MAX_COMMANDS} commands')
        command = _command(command)
        title = _execute(trace, sim, command)
        index = len(result['commands'])
        result['snapshots'].append(_snapshot(trace, sim, index, title))
        result['commands'].append(command)
        result['events'] = _events(trace)
        return _seal(result)
    except RecordError:
        raise
    except (ValueError, TypeError, IndexError, KeyError, RecursionError) as exc:
        raise RecordError(f'invalid command: {exc}') from exc
