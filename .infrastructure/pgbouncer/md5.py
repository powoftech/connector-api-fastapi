import hashlib

password = "postgres_password"
username = "default"
hash_value = hashlib.md5((password + username).encode("utf-8")).hexdigest()
print(f'"{username}" "md5{hash_value}"')
