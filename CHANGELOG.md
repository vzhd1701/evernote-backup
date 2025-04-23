## [1.13.1](https://github.com/vzhd1701/evernote-backup/compare/1.13.0...1.13.1) (2025-04-23)

### Bug Fixes

- skip parsing unused token parameters ([1f199b3](https://github.com/vzhd1701/evernote-backup/commit/1f199b388545b8dc08f3dd2701b2d61de4b294f0))

## [1.13.0](https://github.com/vzhd1701/evernote-backup/compare/1.12.0...1.13.0) (2025-04-19)

### Features

- add --add-metadata option to export mode for embedding metadata into exported notes ([a77f9f2](https://github.com/vzhd1701/evernote-backup/commit/a77f9f21211d56418cb97ee0ce580badecef81eb))
- add --notebook option to export mode for exporting specific notebook(s) ([fdfd7dd](https://github.com/vzhd1701/evernote-backup/commit/fdfd7ddbb4f2a08abe1fee634a46d96773d8cb37))
- add --tag option to export mode for exporting notes with specific tag(s) ([69d4695](https://github.com/vzhd1701/evernote-backup/commit/69d46953f1b308dec836bf9ae7769ccd0558584d))
- add manage check command for db integrity check ([835433b](https://github.com/vzhd1701/evernote-backup/commit/835433b943a831839c61a68df04f2c378a7d9daf))
- add manage list command for listing db content ([d05803c](https://github.com/vzhd1701/evernote-backup/commit/d05803c048d0b4f6f960c9f6fb5a4c7357a2df88))

### Bug Fixes

- avoid crash on any error during note download ([14636b7](https://github.com/vzhd1701/evernote-backup/commit/14636b781c1d6c0425cd7101f532aefc851f3470))

## [1.12.0](https://github.com/vzhd1701/evernote-backup/compare/1.11.0...1.12.0) (2025-04-17)

### Features

- add --api-data option to init-db and reauth for custom API data ([4edd04e](https://github.com/vzhd1701/evernote-backup/commit/4edd04ea707c6401b6fb857ce980c6623ce08f1e)), closes [#129](https://github.com/vzhd1701/evernote-backup/issues/129)
- add options to debug SSL errors ([c28bd70](https://github.com/vzhd1701/evernote-backup/commit/c28bd700222b458623d22de9d8041e4ff4dcf0a0))

### Bug Fixes

- avoid crash on bad string data from server ([70392e6](https://github.com/vzhd1701/evernote-backup/commit/70392e607a0943497cb44ddbdabfe4a6f4dbe328))
- use use_system_ssl_ca flag to init client on manage ping ([e9f8667](https://github.com/vzhd1701/evernote-backup/commit/e9f866726c1a3166579ee811a06161666a0aa52b))

## [1.11.0](https://github.com/vzhd1701/evernote-backup/compare/1.10.0...1.11.0) (2025-04-15)

### Features

- add support for tasks & reminders ([f1ece7a](https://github.com/vzhd1701/evernote-backup/commit/f1ece7afd5e2c58b1260a2e9d2582382d3dada11))

### Bug Fixes

- add hotfix for THttpClient until new thrift version gets released ([386eb24](https://github.com/vzhd1701/evernote-backup/commit/386eb24a944f009dbb4975b929cb25604e5cdd8e)), closes [#130](https://github.com/vzhd1701/evernote-backup/issues/130)
- give warning on corrupt notes without removing notes ([467ee96](https://github.com/vzhd1701/evernote-backup/commit/467ee968bea48db9f6f1730e9fcb450734e113c1))
- mark notes for redownload if they are corrupted in DB ([fb7eedd](https://github.com/vzhd1701/evernote-backup/commit/fb7eeddad0804ca61bc3d55485f163c35fce3df2))
- print log level in console output if it's other than INFO ([aabc5cd](https://github.com/vzhd1701/evernote-backup/commit/aabc5cdf4cd092c43a6743a025d7a7096edf6f36))
- restore china backend login ([4d93d9b](https://github.com/vzhd1701/evernote-backup/commit/4d93d9b7375bfbe4483942afc285abc84a2f9fbb))

## [1.10.0](https://github.com/vzhd1701/evernote-backup/compare/1.9.4...1.10.0) (2025-04-07)

### Features

- add --add-guid option in export mode to include GUID meta for each note ([c4cb1eb](https://github.com/vzhd1701/evernote-backup/commit/c4cb1ebb128924573839a10b586d24ecf124c698)), closes [#66](https://github.com/vzhd1701/evernote-backup/issues/66)
- add --log option for setting log file ([64eb952](https://github.com/vzhd1701/evernote-backup/commit/64eb9521d1f7cde0b6dab17b817f8a0e4f8e0455))

### Bug Fixes

- format reminder-time on export ([eceea64](https://github.com/vzhd1701/evernote-backup/commit/eceea645e444b777d948481b77f4cc076e930518)), closes [#86](https://github.com/vzhd1701/evernote-backup/issues/86)
- skip download for notes that return server side error ([d0fcd23](https://github.com/vzhd1701/evernote-backup/commit/d0fcd23e573442e2a56279e3b2cf1174a0dd84c1))

## [1.9.4](https://github.com/vzhd1701/evernote-backup/compare/v1.9.3...1.9.4) (2025-04-06)

### Bug Fixes

- drop evernote sandbox backend ([d4b99c7](https://github.com/vzhd1701/evernote-backup/commit/d4b99c76d82800dbcdd75f87b6614f94352faeb9))
- update yinxiang API key ([1d43fa4](https://github.com/vzhd1701/evernote-backup/commit/1d43fa47d1a78d86f7d759a3a9ab8be4b1161137))
- use oauth login for evernote and password login for yinxiang ([4930005](https://github.com/vzhd1701/evernote-backup/commit/4930005a3cf25fe30eed0e1173a6e2321f4289ce))

## [1.9.3](https://github.com/vzhd1701/evernote-backup/compare/1.9.3...v1.9.3) (2023-10-18)

### Bug Fixes

- add support for negative timestamps (close [#38](https://github.com/vzhd1701/evernote-backup/issues/38)) ([#48](https://github.com/vzhd1701/evernote-backup/issues/48)) ([244440d](https://github.com/vzhd1701/evernote-backup/commit/244440d6dfec8873159c77d741c5b01cecc2cc20))
- change notebooks export log message to avoid confusion ([0a5840d](https://github.com/vzhd1701/evernote-backup/commit/0a5840d980c0d8b554b67fdf3e1a56d184d1ba79)), closes [#52](https://github.com/vzhd1701/evernote-backup/issues/52)

## [1.9.2](https://github.com/vzhd1701/evernote-backup/compare/1.9.1...1.9.2) (2022-08-23)

### Bug Fixes

- fix crash on repeated export with long filenames ([692a93a](https://github.com/vzhd1701/evernote-backup/commit/692a93ab168d7bfa2bd72dccf8856999b367be52)), closes [#26](https://github.com/vzhd1701/evernote-backup/issues/26)

## [1.9.1](https://github.com/vzhd1701/evernote-backup/compare/1.9.0...1.9.1) (2022-08-20)

### Bug Fixes

- limit export filename length to 255 bytes ([33cfe1b](https://github.com/vzhd1701/evernote-backup/commit/33cfe1b95f6aceec01972c56edf78940f42093a8)), closes [#15](https://github.com/vzhd1701/evernote-backup/issues/15)

## [1.9.0](https://github.com/vzhd1701/evernote-backup/compare/1.8.1...1.9.0) (2022-05-17)

### Features

- add --overwrite flag to export mode ([5a88b76](https://github.com/vzhd1701/evernote-backup/commit/5a88b76f9d6e92cd66549cb65e4715473a0dd3c3)), closes [#19](https://github.com/vzhd1701/evernote-backup/issues/19)

## [1.8.1](https://github.com/vzhd1701/evernote-backup/compare/1.8.0...1.8.1) (2022-05-10)

### Bug Fixes

- hide current item name on progress to avoid glitches ([19925b4](https://github.com/vzhd1701/evernote-backup/commit/19925b46bebe3d914c3e0fd723ff517e58cd0443)), closes [#18](https://github.com/vzhd1701/evernote-backup/issues/18)

## [1.8.0](https://github.com/vzhd1701/evernote-backup/compare/1.7.1...1.8.0) (2022-04-22)

### Features

- add --oauth-host option ([0b6b8a6](https://github.com/vzhd1701/evernote-backup/commit/0b6b8a60a29a07af0a35c00c8bcec7b65c9c0868))

## [1.7.1](https://github.com/vzhd1701/evernote-backup/compare/1.7.0...1.7.1) (2022-02-14)

### Bug Fixes

- add index to speed up download with >10k notes DB ([2dbb599](https://github.com/vzhd1701/evernote-backup/commit/2dbb599ad251f19b21684c3f7f30d156b78639e3)), closes [#14](https://github.com/vzhd1701/evernote-backup/issues/14)

## [1.7.0](https://github.com/vzhd1701/evernote-backup/compare/1.6.8...1.7.0) (2022-01-31)

### Features

- add --no-export-date option ([030ddfc](https://github.com/vzhd1701/evernote-backup/commit/030ddfca9b06767afed2183cc86bd69625ad4caa))

## [1.6.8](https://github.com/vzhd1701/evernote-backup/compare/1.6.7...1.6.8) (2022-01-02)

### Bug Fixes

- prevent memory leak on export ([19e9430](https://github.com/vzhd1701/evernote-backup/commit/19e94303bf6927df9b627e15f5f3367399bd5981))

## [1.6.7](https://github.com/vzhd1701/evernote-backup/compare/1.6.6...1.6.7) (2021-12-31)

### Bug Fixes

- add support for long filenames on export ([8bea1e6](https://github.com/vzhd1701/evernote-backup/commit/8bea1e614ce82455fed64f610c35996317830669))

## [1.6.6](https://github.com/vzhd1701/evernote-backup/compare/1.6.5...1.6.6) (2021-10-15)

### Bug Fixes

- add support for notes from the distant future ([d352455](https://github.com/vzhd1701/evernote-backup/commit/d352455c9220fdb7911894456d67ea93caf8760f)), closes [#4](https://github.com/vzhd1701/evernote-backup/issues/4)

## [1.6.5](https://github.com/vzhd1701/evernote-backup/compare/1.6.4...1.6.5) (2021-09-09)

### Bug Fixes

- add download retry on bad data from server ([7baf061](https://github.com/vzhd1701/evernote-backup/commit/7baf061054ceba27a9d9992943b9967505fea004))

## [1.6.4](https://github.com/vzhd1701/evernote-backup/compare/1.6.3...1.6.4) (2021-08-30)

### Bug Fixes

- add support for shared notebooks with tags ([0e4e17c](https://github.com/vzhd1701/evernote-backup/commit/0e4e17c8a381bb7cb3db71940e0bb7047cfdbdd0))

## [1.6.3](https://github.com/vzhd1701/evernote-backup/compare/1.6.2...1.6.3) (2021-08-28)

### Bug Fixes

- add memory limit when downloading notes ([aa4df00](https://github.com/vzhd1701/evernote-backup/commit/aa4df0079b7d3d5d564e74a924c20e7f4b725609))
- add more log messages ([b2fdf11](https://github.com/vzhd1701/evernote-backup/commit/b2fdf119f1b1fce9c32a9948cb97aecd0f2c841a))
- add more log messages ([59c13e1](https://github.com/vzhd1701/evernote-backup/commit/59c13e1e3b292fc554bdc533f5661679b0b81fd4))
- improve handling exceptions when downloading notes ([8c45166](https://github.com/vzhd1701/evernote-backup/commit/8c451668acb8c9918295feec27dc5f79d74b571e))

## [1.6.2](https://github.com/vzhd1701/evernote-backup/compare/1.6.1...1.6.2) (2021-08-24)

### Bug Fixes

- fix support for linked notebooks ([4f4f928](https://github.com/vzhd1701/evernote-backup/commit/4f4f9286639745a5a4aa2410302d28a981c6bac5))

## [1.6.1](https://github.com/vzhd1701/evernote-backup/compare/1.6.0...1.6.1) (2021-08-23)

### Bug Fixes

- add support for linked notebooks ([3bf3ef8](https://github.com/vzhd1701/evernote-backup/commit/3bf3ef8279fb36b9872791a775ddb352b49e51ea))

## [1.6.0](https://github.com/vzhd1701/evernote-backup/compare/1.5.1...1.6.0) (2021-08-09)

### Features

- add --verbose output option ([45051c3](https://github.com/vzhd1701/evernote-backup/commit/45051c34cb2b350939ae7aa563355c1649bd0dc9))
- add debug logging on sync & export ([b1b2dff](https://github.com/vzhd1701/evernote-backup/commit/b1b2dffcf9ebb5594a3491e641ebc3b285c73102))

### Bug Fixes

- typos ([e7bd437](https://github.com/vzhd1701/evernote-backup/commit/e7bd4379c6827be0d91c17a4cb49f78d4259a774))

## [1.5.1](https://github.com/vzhd1701/evernote-backup/compare/1.5.0...1.5.1) (2021-06-09)

### Bug Fixes

- improve performance on big sync, e.g. >1k notes ([03fc4c4](https://github.com/vzhd1701/evernote-backup/commit/03fc4c4e94dd37bb50d139a211cd182d2b9ee0e6))

## [1.5.0](https://github.com/vzhd1701/evernote-backup/compare/1.4.1...1.5.0) (2021-06-07)

### Features

- convert hardcoded config variables into cli options ([fecf49a](https://github.com/vzhd1701/evernote-backup/commit/fecf49aa150f3375b4a3b94b5a6ec72b2ff6a038))

## [1.4.1](https://github.com/vzhd1701/evernote-backup/compare/1.4.0...1.4.1) (2021-05-08)

### Bug Fixes

- make init-db return early if database exists ([631b948](https://github.com/vzhd1701/evernote-backup/commit/631b948aa1d9a9160fd39cab407b5136dfdee992))

## [1.4.0](https://github.com/vzhd1701/evernote-backup/compare/1.3.1...1.4.0) (2021-05-01)

### Features

- add Docker support ([47747f1](https://github.com/vzhd1701/evernote-backup/commit/47747f1aae9b53df63dccebfed55b1f89a42d404))

## [1.3.1](https://github.com/vzhd1701/evernote-backup/compare/1.3.0...1.3.1) (2021-04-30)

### Bug Fixes

- improve logger compatability ([047211d](https://github.com/vzhd1701/evernote-backup/commit/047211d7c33e138e1711316c7adaf446c856bd49))

## [1.3.0](https://github.com/vzhd1701/evernote-backup/compare/1.2.0...1.3.0) (2021-04-29)

### Features

- make exported notes sorted ([9135822](https://github.com/vzhd1701/evernote-backup/commit/91358220daa5cfc3c19b6e9e92bc6094f5d075b5))

## [1.2.0](https://github.com/vzhd1701/evernote-backup/compare/1.1.0...1.2.0) (2021-04-28)

### Features

- add database update routine ([79fc694](https://github.com/vzhd1701/evernote-backup/commit/79fc694854c764808ec0bb48a10c2ca1df223e89))
- change notes storage mechanism ([43ff41e](https://github.com/vzhd1701/evernote-backup/commit/43ff41ebcf9077b686dcc719025632b52535bcd4))

## [1.1.0](https://github.com/vzhd1701/evernote-backup/compare/1.0.0...1.1.0) (2021-04-27)

### Features

- add OAuth login option ([c70d577](https://github.com/vzhd1701/evernote-backup/commit/c70d57775d480a97d7a8d990525ea906881f94a8))

## [1.0.0](https://github.com/vzhd1701/evernote-backup/compare/758dd898e95e2fe09cbdf80da2ee46c728f6369b...1.0.0) (2021-04-24)

### Features

- initialize repository ([758dd89](https://github.com/vzhd1701/evernote-backup/commit/758dd898e95e2fe09cbdf80da2ee46c728f6369b))
