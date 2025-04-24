import sys
import bcrypt

password = sys.argv[1]
print("Entered password:", password)
pwd_bytes = password.encode('utf-8')
gen_salt = bcrypt.gensalt()
new_pass = bcrypt.hashpw(pwd_bytes, gen_salt).decode('utf-8')
print(new_pass)
