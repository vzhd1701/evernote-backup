### [1.9.2](https://github.com/vzhd1701/evernote-backup/compare/1.9.1...1.9.2) (2022-08-23)

### Bug Fixes

- fix crash on repeated export with long filenames ([692a93a](https://github.com/vzhd1701/evernote-backup/commit/692a93ab168d7bfa2bd72dccf8856999b367be52)), closes [#26](https://github.com/vzhd1701/evernote-backup/issues/26)

### [1.9.1](https://github.com/vzhd1701/evernote-backup/compare/1.9.0...1.9.1) (2022-08-20)

### Bug Fixes

- limit export filename length to 255 bytes ([33cfe1b](https://github.com/vzhd1701/evernote-backup/commit/33cfe1b95f6aceec01972c56edf78940f42093a8)), closes [#15](https://github.com/vzhd1701/evernote-backup/issues/15)

## [1.9.0](https://github.com/vzhd1701/evernote-backup/compare/1.8.1...1.9.0) (2022-05-17)

### Features

- add --overwrite flag to export mode ([5a88b76](https://github.com/vzhd1701/evernote-backup/commit/5a88b76f9d6e92cd66549cb65e4715473a0dd3c3)), closes [#19](https://github.com/vzhd1701/evernote-backup/issues/19)

### [1.8.1](https://github.com/vzhd1701/evernote-backup/compare/1.8.0...1.8.1) (2022-05-10)

### Bug Fixes

- hide current item name on progress to avoid glitches ([19925b4](https://github.com/vzhd1701/evernote-backup/commit/19925b46bebe3d914c3e0fd723ff517e58cd0443)), closes [#18](https://github.com/vzhd1701/evernote-backup/issues/18)

## [1.8.0](https://github.com/vzhd1701/evernote-backup/compare/1.7.1...1.8.0) (2022-04-22)

### Features

- add --oauth-host option ([0b6b8a6](https://github.com/vzhd1701/evernote-backup/commit/0b6b8a60a29a07af0a35c00c8bcec7b65c9c0868))

### [1.7.1](https://github.com/vzhd1701/evernote-backup/compare/1.7.0...1.7.1) (2022-02-14)

### Bug Fixes

- add index to speed up download with >10k notes DB ([2dbb599](https://github.com/vzhd1701/evernote-backup/commit/2dbb599ad251f19b21684c3f7f30d156b78639e3)), closes [#14](https://github.com/vzhd1701/evernote-backup/issues/14)

## [1.7.0](https://github.com/vzhd1701/evernote-backup/compare/1.6.8...1.7.0) (2022-01-31)

### Features

- add --no-export-date option ([030ddfc](https://github.com/vzhd1701/evernote-backup/commit/030ddfca9b06767afed2183cc86bd69625ad4caa))

### [1.6.8](https://github.com/vzhd1701/evernote-backup/compare/1.6.7...1.6.8) (2022-01-02)

### Bug Fixes

- prevent memory leak on export ([19e9430](https://github.com/vzhd1701/evernote-backup/commit/19e94303bf6927df9b627e15f5f3367399bd5981))

### [1.6.7](https://github.com/vzhd1701/evernote-backup/compare/1.6.6...1.6.7) (2021-12-31)

### Bug Fixes

- add support for long filenames on export ([8bea1e6](https://github.com/vzhd1701/evernote-backup/commit/8bea1e614ce82455fed64f610c35996317830669))

### [1.6.6](https://github.com/vzhd1701/evernote-backup/compare/1.6.5...1.6.6) (2021-10-15)

### Bug Fixes

- add support for notes from the distant future ([d352455](https://github.com/vzhd1701/evernote-backup/commit/d352455c9220fdb7911894456d67ea93caf8760f)), closes [#4](https://github.com/vzhd1701/evernote-backup/issues/4)

### [1.6.5](https://github.com/vzhd1701/evernote-backup/compare/1.6.4...1.6.5) (2021-09-09)

### Fix

- add download retry on bad data from server

### [1.6.4](https://github.com/vzhd1701/evernote-backup/compare/1.6.3...1.6.4) (2021-08-30)

### Fix

- add support for shared notebooks with tags

### [1.6.3](https://github.com/vzhd1701/evernote-backup/compare/1.6.2...1.6.3) (2021-08-28)

### Fix

- add memory limit when downloading notes
- improve handling exceptions when downloading notes
- add more log messages
- add more log messages

### Refactor

- move default config into single import

### [1.6.2](https://github.com/vzhd1701/evernote-backup/compare/1.6.1...1.6.2) (2021-08-24)

### Fix

- fix support for linked notebooks

### [1.6.1](https://github.com/vzhd1701/evernote-backup/compare/1.6.0...1.6.1) (2021-08-23)

### Fix

- add support for linked notebooks

### [1.6.0](https://github.com/vzhd1701/evernote-backup/compare/1.5.1...1.6.0) (2021-08-09)

### Feat

- add debug logging on sync & export
- add --verbose output option

### Fix

- typos

### [1.5.1](https://github.com/vzhd1701/evernote-backup/compare/1.5.0...1.5.1) (2021-06-09)

### Fix

- improve performance on big sync, e.g. >1k notes

### [1.5.0](https://github.com/vzhd1701/evernote-backup/compare/1.4.1...1.5.0) (2021-06-07)

### Feat

- convert hardcoded config variables into cli options

### [1.4.1](https://github.com/vzhd1701/evernote-backup/compare/1.4.0...1.4.1) (2021-05-08)

### Fix

- make init-db return early if database exists

### [1.4.0](https://github.com/vzhd1701/evernote-backup/compare/1.3.1...1.4.0) (2021-05-01)

### Feat

- add Docker support

### [1.3.1](https://github.com/vzhd1701/evernote-backup/compare/1.3.0...1.3.1) (2021-04-30)

### Fix

- improve logger compatability

### [1.3.0](https://github.com/vzhd1701/evernote-backup/compare/1.2.0...1.3.0) (2021-04-29)

### Feat

- make exported notes sorted

### Refactor

- add type hints
- dedicate network_retry decorator to store functions

### [1.2.0](https://github.com/vzhd1701/evernote-backup/compare/1.1.0...1.2.0) (2021-04-28)

### Feat

- add database update routine
- change notes storage mechanism

### Refactor

- move parameters into config

### [1.1.0](https://github.com/vzhd1701/evernote-backup/compare/1.0.0...1.1.0) (2021-04-27)

### Feat

- add OAuth login option

## 1.0.0 (2021-04-24)
