# E2EE decision required

The current messaging implementation uses authenticated TLS/WSS and stores
plaintext message bodies in PostgreSQL. End-to-end encryption must replace the
message body contract before production messaging is advertised as private.

## Recommended policy

- Generate a per-device identity key in the browser using audited Web Crypto or
  libsodium primitives.
- Keep private keys out of the API, PostgreSQL, Redis, logs, and localStorage.
- Store only public device keys and encrypted message envelopes on the server.
- Encrypt a message separately for every active device in its conversation.
- Use a recovery phrase to encrypt a key backup locally before uploading it;
  the server must never receive the recovery phrase.
- Revoking a device rotates conversation keys and stops delivery to that device.
- Search is client-side over locally decrypted history; server-side plaintext
  search is removed.

## Required product decision

Approve or reject the recommended recovery-phrase model. Rejecting recovery
means losing every device key permanently loses access to the corresponding
messages. After approval, the API needs device-key, key-bundle, encrypted
envelope, rotation, and device-revocation contracts before implementation.
