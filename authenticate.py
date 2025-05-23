from fastapi import UploadFile
from db_op import DB
import bcrypt
import base64

class Authent:
    def hash_password(password):
        pwd_bytes = password.encode('utf-8')
        gen_salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, gen_salt)

    def verify_password(plain_password, hashed_password):
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)

    def authenticate_user(db: DB, username: str, password: str):
        user = db.get_user_by_email(username)
        if not user:
            return False
        if not Authent.verify_password(password, user.password):
            return False
        return user

    async def authenticate_file(file: UploadFile, size, filetype: list = None) -> str:
        if file.size < 1 or file.size > size:
            raise Exception(f"file size have to atleast 1 KB to utmost {size / 1024}KB")

        if filetype is not None:
            ext = file.content_type.split('/')[1]
            if ext not in filetype:
                raise Exception("invalid file type")
        file_bytes = await file.read()
        encode_image = base64.b64encode(file_bytes).decode("utf-8")
        return encode_image
