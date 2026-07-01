# purchase_id:str=generate_uuid()
#         ui_id=generate_uuid()
#         items_toadd=[]
#         pricing_toadd=[]
#         stl_toadd=[]

#         total_items_stocks=0
#         total_items_amount=0
#         total_items_gst=0
#         total_items_count=len(data.items)




# for item in data.items:
#             pur_item_id=generate_uuid()
#             items_toadd.append(
#                 PurchaseItems(
#                     id=pur_item_id,
#                     purchase_id=purchase_id,
#                     product_id=item.product_id,
#                     variant_id=item.variant_id,
#                     batch_id=item.batch_id,
#                     serialno_id=item.serialno_id,
#                     gst=item.gst,
#                     stocks=item.stocks,
#                     stocks_before=0,
#                     stocks_after=item.stocks,
#                     serial_numbers=item.serial_numbers
#                 )
#             )

#             pricing_id=generate_uuid()
#             pricing_toadd.append(
#                 PurchaseItemsPricing(
#                     pricing_id=pricing_id,
#                     purchase_id=purchase_id,
#                     purchase_item_id=pur_item_id,
#                     buy_price=item.pricing_infos.buy_price,
#                     sell_price=item.pricing_infos.sell_price

#                 )
#             )

#             if item.storage_location_infos:
#                 stl_id=generate_uuid()
#                 stl_toadd.append(
#                     PurchaseItemsStoragelocation(
#                         storage_location_id=stl_id,
#                         purchase_item_id=pur_item_id,
#                         purchase_id=purchase_id,
#                         name=item.storage_location_infos.name
#                     )
#                 )

#             total_items_stocks+=item.stocks
#             total_items_amount+=1
#             total_items_gst+=int(item.gst.split("%")[0]) if item.gst else 0

        

#         purchase_toadd=Purchase(
#             id=purchase_id,
#             ui_id=ui_id,
#             shop_id=data.shop_id,
#             supplier_id=data.supplier_id,
#             type=data.type,
#             purchase_view=True,
#             date=data.purchase_date,
#             item_infos=PurchaseItemInfos(
#                 total_amounts=total_items_amount,total_stocks=total_items_stocks,
#                 total_gst=f"{total_items_gst}%",total_items=total_items_count
#             ).model_dump(mode="json"),
#             charges_infos=data.charges_infos.model_dump(mode="json"),
#             calculation_infos=data.calculation_infos.model_dump(mode="json"),
#             payment_infos=[pi.model_dump(mode="json") for pi in data.payment_infos]
#         )

#         purchase_repo_obj=PurchaseRepo(session=self.session)
#         pur_add_res=await purchase_repo_obj.create_bulk_purchase(data=[purchase_toadd])
#         ic(pur_add_res)
#         if pur_add_res:
#             await purchase_repo_obj.create_bulk_items(data=items_toadd)
#             await purchase_repo_obj.create_bulk_pricing(data=pricing_toadd)
#             if stl_toadd:
#                 await purchase_repo_obj.create_bulk_stl(data=stl_toadd)
#         return True




sampel_data=[
    {
        "id":1,
        "variant_id":11,
        "batch_id":12,
        
    },
    {
        "id":1,
        "variant_id":22,
        "batch_id":33,
        
    },
    {
        "id":1,
        "variant_id":1,
        "batch_id":11,
        
    },
    {
        "id":1,
        "variant_id":0,
        "batch_id":1,
        
    },
    
]


validated_data={}
ERROR=False
for data in sampel_data:
    if data['id'] not in validated_data:
        validated_data[data['id']]=[]
    
    else:
        validated_data_info=validated_data[data['id']]
        inc_variant_id=data.get("variant_id",None)
        inc_batch_id=data.get("batch_id",None)

        for inside_data in validated_data_info:
            v_variant_id=inside_data.get("variant_id",None)
            v_batch_id=inside_data.get("batch_id",None)

            if v_variant_id==inc_variant_id:
                if v_batch_id==inc_batch_id:
                    print("same prodcut with same variant or batch id could not be added")
                    ERROR=True
                    break
    if ERROR:
        print("Error occured")
        break
    validated_data[data['id']].append(data)

print(validated_data)

