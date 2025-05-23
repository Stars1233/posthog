import { PluginEvent } from '@posthog/plugin-scaffold'
import { createHash } from 'crypto'

import { LegacyTransformationPluginMeta } from '../../types'

// From UUID Namespace RFC (https://datatracker.ietf.org/doc/html/rfc4122)
const NAMESPACE_OID = '6ba7b812-9dad-11d1-80b4-00c04fd430c8'

const byteToHex: string[] = []

for (let i = 0; i < 256; ++i) {
    byteToHex.push((i + 0x100).toString(16).slice(1))
}

function stringifyUUID(arr: Buffer) {
    // Forked from https://github.com/uuidjs/uuid (MIT)
    // Copyright (c) 2010-2020 Robert Kieffer and other contributors
    return (
        byteToHex[arr[0]] +
        byteToHex[arr[1]] +
        byteToHex[arr[2]] +
        byteToHex[arr[3]] +
        '-' +
        byteToHex[arr[4]] +
        byteToHex[arr[5]] +
        '-' +
        byteToHex[arr[6]] +
        byteToHex[arr[7]] +
        '-' +
        byteToHex[arr[8]] +
        byteToHex[arr[9]] +
        '-' +
        byteToHex[arr[10]] +
        byteToHex[arr[11]] +
        byteToHex[arr[12]] +
        byteToHex[arr[13]] +
        byteToHex[arr[14]] +
        byteToHex[arr[15]]
    ).toLowerCase()
}

export function processEvent(event: PluginEvent, { config }: LegacyTransformationPluginMeta) {
    if (!event.timestamp) {
        // posthog-js sends events without a timestamp, but with an offset and a UUID.
        // Because the UUID is generated by the SDK, we can silently ignore these events.
        // For other SDKs, log an info log with the library name.
        const lib = event.properties?.$lib || 'unknown'
        if (lib !== 'web') {
            console.info(
                `Received event from "${lib}" without a timestamp, the event will not be processed because deduping will not work.`
            )
        }

        return event
    }

    // Create a hash of the relevant properties of the event
    const stringifiedProps = config.dedupMode === 'All Properties' ? `_${JSON.stringify(event.properties)}` : ''
    const hash = createHash('sha1')
    const eventKeyBuffer = hash
        .update(
            `${NAMESPACE_OID}_${event.team_id}_${event.distinct_id}_${event.event}_${event.timestamp}${stringifiedProps}`
        )
        .digest()

    // Convert to UUID v5 spec
    eventKeyBuffer[6] = (eventKeyBuffer[6] & 0x0f) | 0x50
    eventKeyBuffer[8] = (eventKeyBuffer[8] & 0x3f) | 0x80

    event.uuid = stringifyUUID(eventKeyBuffer)
    return event
}
