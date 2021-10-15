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
