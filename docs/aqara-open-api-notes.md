# Aqara API implementation notes

Last reviewed: 2026-09-03

## Authoritative documentation

Use the current Aqara Developer Platform V3 documentation for implementation details:

- API overview: https://opendoc.aqara.com/en/docs/developmanual/apiIntroduction/APIUsageGuide.html
- Trait API: https://opendoc.aqara.com/en/docs/developmanual/apiDocument/FunctionManagement-trait.html
- Trait push API: https://opendoc.aqara.com/en/docs/developmanual/messagePush/messagePushAPI-trait.html
- Push formats: https://opendoc.aqara.com/en/docs/developmanual/messagePush/messagePushFormat.html
- Push modes: https://opendoc.aqara.com/en/docs/developmanual/messagePush/messagePushMode.html
- Supported traits: https://opendoc.aqara.com/en/docs/developmanual/apiDocument/trait-codes.html

The V3 endpoint is `https://${region}/v3.0/open/api`. Requests select an operation through the
`intent` field.

## Resource and trait push

Resource subscriptions use `config.resource.subscribe`. Their RocketMQ messages have type
`resource_report` and identify values by `subjectId` and `resourceId`.

Trait subscriptions use `spec.config.trait.subscribe`. Each subscription contains a `deviceId`,
an optional `attach`, and `codePaths` formatted as `endpointId.functionCode.traitCode`.
Unsubscription uses `spec.config.trait.unsubscribe` with the same device and code paths.

Trait changes are delivered as `spec_report`. Each item contains `deviceId`, `endpointId`,
`functionCode`, `traitCode`, a typed `value`, `time`, `statusCode`, `triggerSource`, and `attach`.
Do not assume trait values are strings.

RocketMQ retains messages generated during the preceding 12 hours. The bridge snapshot is still
an in-memory latest-value view, not a complete device-state response.

## Capability discovery

`spec.query.specdevice.config` returns the endpoint/function/trait tree for devices whose model
starts with `aqara.matter`. Trait metadata includes `readable`, `writable`, and `subscribable`.
Prefer these device-specific flags when adding generic trait support.

`spec.query.trait` accepts at most 50 traits per request. `spec.write.trait` documents limits by
device count and should be checked per returned item because request acceptance does not prove
that the device performed the operation.

The U200 traits currently used by this integration (`Reachable`, `BatReplacementNeeded`,
`Rechargeable`, `CurrentVoltage`, `BatPercentRemaining`, `LockState`, and `DoorState`) are listed
as reportable in the public trait catalog. Device-specific `subscribable` metadata remains the
stronger runtime authority.

## Historical repositories

The following Aqara repositories are useful background but are not current V3 specifications:

- `aqara/aiot-gateway-local-api`: 2017 UDP port 9898 protocol for legacy Zigbee gateways.
- `aqara/lumi-gateway-local-api`: 2017 fork of the same legacy local protocol.
- `aqara/aiot-cloud-development`: 2017-era cloud API and HTTP push documentation.
- `aqara/aiot-open-api`: Java cloud SDK last updated in 2022, covering older V1/V2 APIs.

Do not derive V3 request signatures, token behavior, trait payloads, or modern device support from
these repositories without confirming the current platform documentation.
