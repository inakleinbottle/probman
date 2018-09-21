
import base64



def decode(data):
    return base64.b85decode(data.encode('ascii'))
 
def extract_figs(path, attachments):
    for attachment in attachments:
        fname, data = attachment
        with open(path / fname, 'wb') as f:
            f.write(decode(data))
