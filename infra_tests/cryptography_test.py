from cryptography.fernet import Fernet

key = Fernet.generate_key()

cipher_suite = Fernet(key)
ciphered_text = cipher_suite.encrypt(b"This is a password")
print("ciphered text:", ciphered_text)
with open("sqlkey.txt", "w") as f:
   f.write("key " + key.decode("utf-8"))
   f.write("cipher " + ciphered_text.decode("utf-8"))


unciphered_text = (cipher_suite.decrypt(ciphered_text))
print("unciphered text:", unciphered_text)