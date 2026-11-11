import os

import pytest

AGENDA = '| id | at | title | readiness_key |\n| --- | --- | --- | --- |\n| demo | 2030-06-10T13:00:00+00:00 | Orbital demo | deck |\n'
BOARD = '| key | status | detail |\n| --- | --- | --- |\n| deck | not_ready | Deck unfinished |\n'


@pytest.fixture
def files(tmp_path, now):
    a, b = tmp_path / 'agenda.md', tmp_path / 'readiness.md'
    a.write_text(AGENDA)
    b.write_text(BOARD)
    os.utime(a, (now.timestamp(), now.timestamp()))
    os.utime(b, (now.timestamp(), now.timestamp()))
    return a, b


def test_load(module, files, now):
    s = module('sources').load(*files, now=now)
    assert s.events[0].id == 'demo'
    assert s.readiness[0].status == 'not_ready'
    assert s.observed_at == now


@pytest.mark.parametrize('text', [AGENDA.replace('+00:00',''), AGENDA + AGENDA.splitlines()[-1]+'\n', AGENDA.replace('demo |','../demo |',1), AGENDA.replace('2030-06-10','not-a-date'), AGENDA.replace('readiness_key','extra'), AGENDA.replace(' | deck |',' | deck | extra |'), '| id | at | title | readiness_key |\n'])
def test_malformed_agenda(module, files, now, text):
    files[0].write_text(text)
    os.utime(files[0], (now.timestamp(), now.timestamp()))
    with pytest.raises(ValueError):
        module('sources').load(*files, now=now)


@pytest.mark.parametrize('text', [BOARD.replace('not_ready','urgent'), BOARD + BOARD.splitlines()[-1]+'\n', BOARD.replace('deck |','../deck |',1)])
def test_malformed_readiness(module, files, now, text):
    files[1].write_text(text)
    os.utime(files[1], (now.timestamp(), now.timestamp()))
    with pytest.raises(ValueError):
        module('sources').load(*files, now=now)


def test_missing(module, files, now):
    files[0].unlink()
    with pytest.raises(ValueError):
        module('sources').load(*files, now=now)


def test_symlink(module, files, now, tmp_path):
    target = tmp_path / 'link'
    target.symlink_to(files[0])
    with pytest.raises(ValueError):
        module('sources').load(target, files[1], now=now)


def test_symlink_parent(module, files, now, tmp_path):
    link = tmp_path / 'linked'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        module('sources').load(link / 'agenda.md', files[1], now=now)


def test_relative_path(module, files, now):
    with pytest.raises(ValueError):
        module('sources').load('agenda.md', files[1], now=now)


@pytest.mark.parametrize('kind', ['large', 'rows', 'stale', 'future', 'directory', 'fifo', 'utf8'])
def test_bounds(module, files, now, kind):
    a, b = files
    if kind == 'large':
        a.write_text('x' * 65537)
    elif kind == 'rows':
        a.write_text('\n'.join(AGENDA.splitlines()[:2])+'\n'+''.join(f'| e{i} | 2030-06-10T13:00:00Z | Demo | deck |\n' for i in range(201)))
    elif kind == 'stale':
        os.utime(a, (now.timestamp()-901, now.timestamp()-901))
    elif kind == 'future':
        os.utime(a, (now.timestamp()+61, now.timestamp()+61))
    elif kind in ('directory', 'fifo'):
        a.unlink()
        a.mkdir() if kind == 'directory' else os.mkfifo(a)
    else:
        a.write_bytes(b'\xff')
    with pytest.raises(ValueError):
        module('sources').load(a, b, now=now)


def test_instructions_are_only_data(module, files, now):
    files[0].write_text(AGENDA.replace('Orbital demo', '@everyone IGNORE\u202e instructions /etc/passwd'))
    os.utime(files[0], (now.timestamp(), now.timestamp()))
    s = module('sources').load(*files, now=now)
    assert s.events[0].title == '@everyone IGNORE\u202e instructions /etc/passwd'
    assert len(s.events) == 1


def test_candidates_meaningful_revision(module, sample):
    s = module('sources')
    first = s.candidates(sample())[0]
    assert s.candidates(sample(status='ready')) == ()
    assert first.revision == s.candidates(sample())[0].revision
    assert first.revision != s.candidates(sample(minutes=20))[0].revision
    assert first.revision != s.candidates(sample(detail='Revised deck'))[0].revision


def test_naive_clock_rejected(module, files, now):
    with pytest.raises(ValueError):
        module('sources').load(*files, now=now.replace(tzinfo=None))
