# Example

## Setup

```shell
cd example
```

## Commands

```shell
# list all registered commands
bollydog ls --config ./config.yaml

# execute a command directly
bollydog execute ping --config ./config.yaml
bollydog execute echo --config ./config.yaml --text="hello"
bollydog execute pipeline --config ./config.yaml
```

## HTTP Service

```shell
# start service
bollydog service --config ./config.yaml

# health check
curl http://0.0.0.0:8000/api/ping

# echo with params
curl -X POST http://0.0.0.0:8000/api/echo \
  -H 'Content-Type: application/json' \
  -d '{"text": "hello bollydog"}'

# SSE streaming countdown
curl http://0.0.0.0:8000/api/countdown?n=3
```

## Shell

```shell
bollydog shell --config ./config.yaml
```

```python
msg = await hub.execute(BaseCommand.resolve('ping')())
msg.state.result()

msg = await hub.execute(BaseCommand.resolve('echo')(text='hi'))
msg.state.result()
```
