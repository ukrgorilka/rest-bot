# rest-bot

Telegram bot project. The separate relationship feature is documented in [`relationships/README.md`](relationships/README.md).

Relationship commands use plain text with the `отн` prefix (no dot or slash). The old marriage flow has been retired; personal home commands remain separate.


## Проверка проекта

Перед развёртыванием можно выполнить из корня проекта:

```bash
python -m compileall -q .
python -m unittest discover -q
```

Файл [`QUALITY_REVIEW.md`](QUALITY_REVIEW.md) содержит список проверок и известных ограничений релизной сборки.
