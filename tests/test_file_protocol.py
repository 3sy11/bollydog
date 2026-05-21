"""FileProtocol tests — LocalFileProtocol + TOMLFileProtocol, using tmp dir."""
import os
import pytest


async def test_local_file_read_write(tmp_path):
    from bollydog.adapters.file import LocalFileProtocol
    proto = LocalFileProtocol(path=str(tmp_path / 'data'))
    async with proto:
        await proto.write('hello.txt', 'world')
        content = await proto.read('hello.txt')
        assert content == 'world'

async def test_local_file_nested_dir(tmp_path):
    from bollydog.adapters.file import LocalFileProtocol
    proto = LocalFileProtocol(path=str(tmp_path / 'data'))
    async with proto:
        await proto.write('sub/deep/file.txt', 'nested')
        assert await proto.read('sub/deep/file.txt') == 'nested'

async def test_local_file_read_not_found(tmp_path):
    from bollydog.adapters.file import LocalFileProtocol
    proto = LocalFileProtocol(path=str(tmp_path / 'data'))
    async with proto:
        with pytest.raises(FileNotFoundError):
            await proto.read('nope.txt')

async def test_local_file_write_non_string(tmp_path):
    from bollydog.adapters.file import LocalFileProtocol
    proto = LocalFileProtocol(path=str(tmp_path / 'data'))
    async with proto:
        await proto.write('num.txt', 42)
        assert await proto.read('num.txt') == '42'


async def test_toml_read_write(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        await proto.set('app.name', 'bollydog')
        await proto.set('app.version', '1.0')
        assert await proto.get('app.name') == 'bollydog'
        assert await proto.get('app.version') == '1.0'

async def test_toml_read_full(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        await proto.set('x', 1)
        data = await proto.read()
        assert data['x'] == 1

async def test_toml_delete(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        await proto.set('a', 1)
        assert await proto.delete('a') is True
        assert await proto.get('a') is None
        assert await proto.delete('nonexist') is False

async def test_toml_merge(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        await proto.set('db.host', 'localhost', flush=False)
        await proto.set('db.port', 5432, flush=False)
        await proto.merge({'db': {'port': 3306}, 'new': True})
        assert await proto.get('db.port') == 3306
        assert await proto.get('db.host') == 'localhost'
        assert await proto.get('new') is True

async def test_toml_keys(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        await proto.set('a.b', 1, flush=False)
        await proto.set('a.c', 2, flush=False)
        await proto.set('x', 3, flush=False)
        keys = await proto.keys('a')
        assert set(keys) == {'a.b', 'a.c'}
        all_keys = await proto.keys()
        assert 'x' in all_keys

async def test_toml_keys_missing_prefix(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        assert await proto.keys('nonexist') == []

async def test_toml_get_default(tmp_path):
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(tmp_path / 'config.toml'))
    async with proto:
        assert await proto.get('no.such.key', default='fallback') == 'fallback'

async def test_toml_load_existing(tmp_path):
    """Load from existing TOML file on startup."""
    import msgspec
    f = tmp_path / 'existing.toml'
    f.write_bytes(msgspec.toml.encode({'loaded': True}))
    from bollydog.adapters.file import TOMLFileProtocol
    proto = TOMLFileProtocol(path=str(f))
    async with proto:
        assert await proto.get('loaded') is True
