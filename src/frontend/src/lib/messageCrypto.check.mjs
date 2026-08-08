import assert from "node:assert/strict";
import { createRecoveryBackup, decryptEnvelope, encryptMessage, generateIdentity, restoreIdentity } from "./messageCrypto.js";

const sender = await generateIdentity("sender-device");
const recipient = await generateIdentity("recipient-device");
const devices = [
  { id: sender.id, public_key: sender.publicKeyJwk },
  { id: recipient.id, public_key: recipient.publicKeyJwk },
];
const envelope = await encryptMessage("secret message", sender, devices, "conversation-1");
assert.equal(await decryptEnvelope(envelope, recipient, devices, "conversation-1"), "secret message");
assert.equal(await decryptEnvelope(null, null, [], "conversation-1"), null);
assert.equal(await decryptEnvelope(envelope, sender, devices, "conversation-1"), "secret message");
const backup = await createRecoveryBackup(sender, "a sufficiently long recovery phrase");
const restored = await restoreIdentity(backup, "a sufficiently long recovery phrase", sender.id);
assert.equal(await decryptEnvelope(envelope, restored, devices, "conversation-1"), "secret message");
console.log("message crypto checks passed");
