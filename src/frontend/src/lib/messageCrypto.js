const encoder = new TextEncoder();
const decoder = new TextDecoder();
const DB_NAME = "simple-blog-e2ee";
const STORE_NAME = "identity";

function bytesToBase64(bytes) {
  let value = "";
  for (const byte of bytes) value += String.fromCharCode(byte);
  return btoa(value);
}

function base64ToBytes(value) {
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

async function deriveKey(privateKey, publicKey, conversationId) {
  const bits = await crypto.subtle.deriveBits({ name: "ECDH", public: publicKey }, privateKey, 256);
  const shared = await crypto.subtle.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: encoder.encode(conversationId), info: encoder.encode("simple-blog-e2ee-v1") }, shared, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

async function importPublicKey(jwk) {
  return crypto.subtle.importKey("jwk", jwk, { name: "ECDH", namedCurve: "P-256" }, true, []);
}

export async function generateIdentity(id = crypto.randomUUID()) {
  const keyPair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  return { id, privateKey: keyPair.privateKey, publicKey: keyPair.publicKey, publicKeyJwk: await crypto.subtle.exportKey("jwk", keyPair.publicKey) };
}

export async function encryptMessage(text, identity, devices, conversationId) {
  const recipients = await Promise.all(devices.map(async (device) => {
    const key = await deriveKey(identity.privateKey, await importPublicKey(device.public_key), conversationId);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, encoder.encode(text));
    return { device_id: device.id, iv: bytesToBase64(iv), ciphertext: bytesToBase64(new Uint8Array(ciphertext)) };
  }));
  return { version: 1, sender_device_id: identity.id, recipients };
}

export async function decryptEnvelope(envelope, identity, devices, conversationId) {
  const recipient = envelope?.recipients?.find((item) => item.device_id === identity.id);
  const sender = devices.find((device) => device.id === envelope?.sender_device_id);
  if (!recipient || !sender) return null;
  const key = await deriveKey(identity.privateKey, await importPublicKey(sender.public_key), conversationId);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: base64ToBytes(recipient.iv) }, key, base64ToBytes(recipient.ciphertext));
  return decoder.decode(plaintext);
}

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function loadIdentity() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const request = db.transaction(STORE_NAME).objectStore(STORE_NAME).get("current");
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
}

export async function saveIdentity(identity) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const request = db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME).put(identity, "current");
    request.onsuccess = () => resolve(identity);
    request.onerror = () => reject(request.error);
  });
}
