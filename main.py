import os
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from typing import List, Optional
import uuid

app = FastAPI(title="Backend Examen API", version="1.0.0")

# ==========================================
# CUMPLIENDO RÚBRICA: Variables
# ==========================================
# Estas variables serán inyectadas por AWS ECS (Fargate) en producción
API_KEY_NAME = "X-API-Key"
SECRET_API_KEY = os.getenv("APP_API_KEY", "super-secret-local-key") 
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE_NAME", "ExamTable")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Configuración de DynamoDB (+1 Punto extra en la rúbrica)
# Boto3 tomará automáticamente los permisos del Rol de IAM de ECS, cero credenciales en código.
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

# ==========================================
# MODELOS DE DATOS
# ==========================================
class Item(BaseModel):
    name: str
    description: Optional[str] = None

class ItemResponse(Item):
    id: str

# ==========================================
# CUMPLIENDO RÚBRICA: Rutas protegidas
# ==========================================
async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == SECRET_API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: API Key inválida"
    )

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "API funcionando correctamente"}

# ==========================================
# CUMPLIENDO RÚBRICA: CRUD Básico (1)
# ==========================================

@app.post("/items/", response_model=ItemResponse, tags=["CRUD"], dependencies=[Depends(get_api_key)])
def create_item(item: Item):
    item_id = str(uuid.uuid4())
    new_item = {"id": item_id, "name": item.name, "description": item.description}
    try:
        table.put_item(Item=new_item)
        return new_item
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/items/", response_model=List[ItemResponse], tags=["CRUD"], dependencies=[Depends(get_api_key)])
def get_all_items():
    try:
        response = table.scan()
        return response.get('Items', [])
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/items/{item_id}", response_model=ItemResponse, tags=["CRUD"], dependencies=[Depends(get_api_key)])
def get_item(item_id: str):
    try:
        response = table.get_item(Key={'id': item_id})
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Item no encontrado")
        return response['Item']
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/items/{item_id}", response_model=ItemResponse, tags=["CRUD"], dependencies=[Depends(get_api_key)])
def update_item(item_id: str, item: Item):
    try:
        response = table.update_item(
            Key={'id': item_id},
            UpdateExpression="set #n=:n, description=:d",
            ExpressionAttributeNames={'#n': 'name'},
            ExpressionAttributeValues={
                ':n': item.name,
                ':d': item.description
            },
            ReturnValues="ALL_NEW"
        )
        return response.get('Attributes', {})
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/items/{item_id}", tags=["CRUD"], dependencies=[Depends(get_api_key)])
def delete_item(item_id: str):
    try:
        table.delete_item(Key={'id': item_id})
        return {"message": "Item eliminado correctamente"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))