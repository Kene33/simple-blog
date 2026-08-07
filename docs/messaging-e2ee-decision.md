# E2EE decision implemented

The approved E2EE MVP uses authenticated TLS/WSS plus browser-side encryption.
PostgreSQL and Redis receive only opaque encrypted envelopes and public device
keys.

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

## Approved implementation

The recovery-phrase model is approved. Device private keys are held in
IndexedDB, and recovery backups are encrypted with PBKDF2 + AES-GCM before
they can leave the browser. The server never receives the phrase.

The current MVP does not implement a Signal-style ratchet, automatic key
rotation, or server-side plaintext search. Those require an independent audited
protocol before claiming forward secrecy.
