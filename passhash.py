import sys
import bcrypt

pwd_bytes = sys.argv[1].encode('utf-8')
gen_salt = bcrypt.gensalt()
new_pass = bcrypt.hashpw(pwd_bytes, gen_salt).decode('utf-8')

print(new_pass)
