import json
from fastapi import APIRouter, Depends, HTTPException
import logging
import time

from fastapi import Request
from starlette import status

from fast_api_als.database.db_helper import db_helper_session
from fast_api_als.quicksight.s3_helper import s3_helper_client
from fast_api_als.services.authenticate import get_token
from fast_api_als.utils.cognito_client import get_user_role

router = APIRouter()

"""
write proper logging and exception handling
"""

def get_quicksight_data(lead_uuid, item):
    """
            Creates the lead converted data for dumping into S3.
            Args:
                lead_uuid: Lead UUID
                item: Accepted lead info pulled from DDB
            Returns:
                S3 data
    """
    data = {
        "lead_hash": lead_uuid,
        "epoch_timestamp": int(time.time()),
        "make": item['make'],
        "model": item['model'],
        "conversion": 1,
        "postalcode": item.get('postalcode', 'unknown'),
        "dealer": item.get('dealer', 'unknown'),
        "3pl": item.get('3pl', 'unknown'),
        "oem_responded": 1
    }
    return data, f"{item['make']}/1_{int(time.time())}_{lead_uuid}"


@router.post("/conversion")
async def submit(file: Request, token: str = Depends(get_token)):

    logging.info("Recieving data")
    t1 = (int)(time.time()*1000)
    body = await file.body()
    t2 = (int)(time.time()*1000)
    logging.info(f'Recieved data in {t2-t1} ms.')
    try:
        body = json.loads(str(body, 'utf-8'))
    except:
        logging.error("Unable to load data")
        raise HTTPException(status_code=500, detail="Unable to load data")

    if 'lead_uuid' not in body or 'converted' not in body:
        logging.error("lead_uuid or converted are not available.")
        raise HTTPException(status_code = 500, detail="lead_uuid or converted are not available.")
        
        
    lead_uuid = body['lead_uuid']
    converted = body['converted']

    oem, role = get_user_role(token)
    if role != "OEM":
        logging.error("User Not Authorised(role is not oem).")
        raise HTTPException(status_code=401, detail="User Not Authorised")

    is_updated, item = db_helper_session.update_lead_conversion(lead_uuid, oem, converted)
    if is_updated:
        logging.info("Lead Conversion  updated")
        data, path = get_quicksight_data(lead_uuid, item)
        s3_helper_client.put_file(data, path)
        return {
            "status_code": status.HTTP_200_OK,
            "message": "Lead Conversion Status Update"
        }
    else:
        logging.error("Lead Conversion not updated")
        raise HTTPException(status_code=500, detail="Lead Conversion not updated")
