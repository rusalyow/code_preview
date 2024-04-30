#Главная страница
def index(request):
    user_city = request.session.get('user_city', 'Владимир') #получаем город из сессии
    user_storage = Storage.objects.get(storage_name=user_city) #присваиваем пользователю соответствующий склад из базы данных

    #получаем товары для блоков на главной странице
    products_ps = Product.objects.filter(
        category=51,
        stock__warehouse=user_storage,
        stock__quantity__gt=0
    ).exclude(image=None).distinct()[:4]
    products_xbox = Product.objects.filter(
        category=75,
        stock__warehouse=user_storage,
        stock__quantity__gt=0
    ).exclude(image=None).distinct()[:4]
    products_pop = Product.objects.filter(stock__warehouse=user_storage).annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:4]

    #костыли на скорую руку
    cart_count = 0
    cart_items = []
    cart_items_ids = []
    total_cost = 0
    
    if request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first() #получаем корзину пользователя из бд. Можно не сохранять в бд, используя только сессии, но так нужно для потенциальной аналитики.
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            cart_items_ids = cart_items.values_list('product_id', flat=True)
            cart_count = cart_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_cost = sum(item.product.price * item.quantity for item in cart_items)

    context = {
        'city': user_city,
        'products_ps': products_ps,
        'products_xbox': products_xbox,
        'products_pop': products_pop,
        'cart_items': cart_items,
        'cart_items_ids': cart_items_ids,
        'cart_count': cart_count,
        'total_cost': total_cost
    }
    return render(request, 'main/index.html', context)

#функция для получения списка городов из базы данных
def get_cities(request):
    cities = Storage.objects.values_list('storage_name', flat=True).distinct()
    return JsonResponse({'cities': list(cities)})

#устанавливаем город для пользователя, обработка формы
def set_city(request):
    if request.method == 'POST':
        city = request.POST.get('city')
        request.session['user_city'] = city
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

#страница поиска
def search_results(request, query):
    category = None
    products = Product.objects.filter(name__icontains=query) #получаем продукты по ключу
    cart_count = 0
    cart_items = []
    total_cost = 0
    cart_ids = []
    
    if request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first() #можно было написать одну функцию получения корзины для всех страниц. В следующий раз так и сделаю :)
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            cart_ids = cart_items.values_list('product_id', flat=True)
            cart_count = cart_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_cost = sum(item.product.price * item.quantity for item in cart_items)

    user_city = request.session.get('user_city', 'Владимир')
    current_date = datetime.now()
    delivery_date = current_date + timedelta(days=4) #чтобы показывать пользователю примерную дату доставки товара в магазин в случае заказа 

    if request.GET.get('category'): #фильтр по категориям
        category = Category.objects.get(slug=request.GET.get('category'))
        products = Product.objects.filter(name__icontains=query, category=category)

    sort = request.GET.get('sort', 'date') #сортировка
    if sort == 'date':
        products = products.order_by('last_updated')
    elif sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        pass

    category_ids = Product.objects.filter(name__icontains=query).values_list('category', flat=True).distinct() 
    categories = Category.objects.filter(id__in=category_ids) #получаем категории для фильтра

    #пагинация
    products_count = products.count()
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number) 

    user_storage = Storage.objects.get(storage_name=user_city) #получаем склад пользователя из бд
    for product in page_obj:
        product.available_warehouses_count = Stock.objects.filter(product=product,
                                                                  quantity__gt=0).count() #получаем количество товара на складах
        product.stocks = Stock.objects.filter(product=product) #получаем сток продукта
        if user_storage:
            product.is_available = Stock.objects.filter(product=product, warehouse=user_storage,
                                                        quantity__gt=0).exists() #проверяем наличие товара на складе города пользователя
            if not product.is_available:
                order_delivery_date = current_date + timedelta(days=4) #или выводим примерную дату доставки
        else:
            product.is_available = False

    return render(request, 'main/search.html', {
        'products': products,
        'products_count': products_count,
        'delivery_date': delivery_date,
        'page_obj': page_obj,
        'query': query,
        'sort': sort,
        'categories': categories,
        'filter_category': category,
        'city': user_city,
        'cart_items': cart_items,
        'cart_count': cart_count,
        'total_cost': total_cost,
        'cart_ids': cart_ids,
    })

#получение списка городов с помощью сдек апи
def city_search(request):
    query = request.GET.get('query', '')
    url_token = "" 
    response_token = requests.post(url_token)
    data_token = response_token.json()
    token = data_token['access_token']
    url = "	https://api.cdek.ru/v2/location/cities?country_codes=RU&city=" + query
    headers = {
        "Authorization": "bearer" + token,
    }
    response = requests.get(url, headers=headers) #делаем запрос
    data = response.json() 
    cities = []
    for row in data:  #парсим ответ
        url_1 = "https://api.cdek.ru/v2/calculator/tariff"
        data_1 = {
            "from_location": {
                "code": 94
            },
            "to_location": {
                "code": row['code']
            },
            "tariff_code": 137,
            "packages": [
                {
                    "height": 10,
                    "length": 10,
                    "weight": 8000,
                    "width": 10
                }
            ]
        }
        headers = {
            "Authorization": "bearer" + token,
            "Content-Type": "application/json",
        }
        response_1 = requests.post(url_1, headers=headers, json=data_1)
        data_sum1 = response_1.json()

        url_2 = "https://api.cdek.ru/v2/calculator/tariff"
        data_2 = {
            "from_location": {
                "code": 94
            },
            "to_location": {
                "code": row['code']
            },
            "tariff_code": 136,
            "packages": [
                {
                    "height": 10,
                    "length": 10,
                    "weight": 8000,
                    "width": 10
                }
            ]
        }
        response_2 = requests.post(url_2, headers=headers, json=data_2)
        data_sum2 = response_2.json()

        url_postal = f"https://api.cdek.ru/v2/location/postalcodes/?code={row['code']}"
        response_postal = requests.get(url_postal, headers=headers)
        data_postal = response_postal.json()
        try:
            postal_code = data_postal['postal_codes'][0] #получаем индекс 
            url_pochta = f"https://delivery.pochta.ru/v2/calculate/tariff/delivery?json&object=27030&from=600000&to={postal_code}&weight=8000&pack=30" #получаем тарифы почты россии по индексу
            response_pochta = requests.get(url_pochta)
            data_pochta = response_pochta.json()
            pochta_sum = int(data_pochta['items'][0]['tariff']['valnds']) / 100
            pochta_date_max = data_pochta['delivery']['max']
            row['pochta_sum'] = int(pochta_sum)
            row['pochta_date_max'] = pochta_date_max
        except Exception as e:
            print(e)

        try:
            cdek1_sum = data_sum1['delivery_sum'] #сдек цена до двери
            cdek1_date_max = data_sum1['period_max'] #сдек дата до двери
            cdek2_sum = data_sum2['delivery_sum'] #сдек цена до пункта выдачи
            cdek2_date_max = data_sum2['period_max'] #сдек дата до пункта выдачи


            row['cdek1_sum'] = int(cdek1_sum)
            row['cdek1_date_max'] = cdek1_date_max
            row['cdek2_sum'] = int(cdek2_sum)
            row['cdek2_date_max'] = cdek2_date_max

        except Exception as e:
            print(e)

        row['delivery_render'] = render_to_string('main/delivery-items.html', {
            'city': row
        }) #рендерим часть страницы с данными
        cities.append(row)

    return JsonResponse({
        'cities': cities,
    })


#пример рендера через ajax
def calculate_sum(request):
    cost = request.GET.get('cost', '')
    total_cost = 0

    if request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first()
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            total_cost = sum(item.product.price * item.quantity for item in cart_items)

    render_sum = render_to_string('main/sum-items.html', {
        'cost': cost,
        'summa': int(total_cost)+int(cost),
    }) 
    return JsonResponse({
        'render_sum': render_sum,
    })
    return render(request, 'cart/order.html', context)



#webhook на обновление товара
@csrf_exempt
def webhook_update(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        events = data.get('events', [])

        for event in events:
            #если продукт обновлен
            if event.get('action') == 'UPDATE':
                product_href = event.get('meta', {}).get('href')
                if product_href:
                    access_token = ""
                    headers = {
                        "Authorization": access_token,
                        "Accept-Encoding": "gzip",
                        "Content-Type": "application/json",
                    }

                    response = requests.get(product_href, headers=headers)#делаем запрос на измененный продукт
                    data = response.json()
                    #скачиваем изображение товара
                    try:
                        images = requests.get(data['images']['meta']['href'], headers=headers)
                        product_image = requests.get(images.json()['rows'][0]['meta']['downloadHref'], headers=headers)
                        product_image_content = ContentFile(product_image.content, name='product_image.jpg')
                        image_data = product_image_content.read()
                        image_file = BytesIO(image_data)
                        filename = f"{data['id']}.jpg"
                        django_file = InMemoryUploadedFile(image_file, None, filename, 'image/jpeg',
                                                           image_file.getbuffer().nbytes, None)
                    except:
                        django_file = None
                    #обновляем или создаем продукт
                    product, created = Product.objects.update_or_create(
                        moysklad_id=data['id'],
                        defaults={
                            'name': data['name'],
                            'description': data.get('description', ''),
                            'price': data['salePrices'][0]['value'] / 100,
                            'image': django_file,
                            'last_updated': data['updated'],
                        }
                    )

                    return JsonResponse({'status': 'success', 'href': product_href})
            #если продукт создан
            elif event.get('action') == 'CREATE':
                product_href = event.get('meta', {}).get('href')
                if product_href:
                    access_token = ""
                    headers = {
                        "Authorization": access_token,
                        "Accept-Encoding": "gzip",
                        "Content-Type": "application/json",
                    }

                    response = requests.get(product_href, headers=headers)
                    data = response.json()
                    if 'pathName' in data and not data['pathName'].strip():
                        category_name = 'без категории'
                    else:
                        category_name = data['pathName']
                    try:
                        category = Category.objects.filter(name=category_name).get()
                    except:
                        category = Category.objects.create(name=category_name)
                    try:
                        images = requests.get(data['images']['meta']['href'], headers=headers)
                        product_image = requests.get(images.json()['rows'][0]['meta']['downloadHref'], headers=headers)
                        product_image_content = ContentFile(product_image.content, name='product_image.jpg')
                        image_data = product_image_content.read()
                        image_file = BytesIO(image_data)
                        filename = f"{data['id']}.jpg"
                        django_file = InMemoryUploadedFile(image_file, None, filename, 'image/jpeg',
                                                           image_file.getbuffer().nbytes, None)
                    except:
                        django_file = None

                    product, created = Product.objects.update_or_create(
                        moysklad_id=data['id'],
                        defaults={
                            'name': data['name'],
                            'description': data.get('description', ''),
                            'price': data['salePrices'][0]['value'] / 100,
                            'image': django_file,
                            'category': category,
                            'last_updated': data['updated'],
                        }
                    )

                    return JsonResponse({'status': 'success', 'href': product_href})

        return JsonResponse({'status': 'success', 'message': 'No update action found'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


#пример создания нового заказа в мойсклад
def order(request):
    user_city = request.session.get('user_city', 'Владимир')
    #получаем склад. В моем случае количество складов всего 3 и увеления не планируется. В случае, когда количество складов динамично, лушче работать через отдельную функцию.
    if user_city == 'Владимир':
        store = {
            'meta': {'href': 'https://api.moysklad.ru/api/remap/1.2/entity/store/*',
                     'metadataHref': 'https://api.moysklad.ru/api/remap/1.2/entity/store/metadata', 'type': 'store',
                     'mediaType': 'application/json',
                     'uuidHref': 'https://online.moysklad.ru/app/#warehouse/edit?id=*'}}
    elif user_city == 'Ковров':
        store = {
            'meta': {'href': 'https://api.moysklad.ru/api/remap/1.2/entity/store/*',
                     'metadataHref': 'https://api.moysklad.ru/api/remap/1.2/entity/store/metadata', 'type': 'store',
                     'mediaType': 'application/json',
                     'uuidHref': 'https://online.moysklad.ru/app/#warehouse/edit?id=*'}}
    elif user_city == 'Камешково':
        store = {
            'meta': {'href': 'https://api.moysklad.ru/api/remap/1.2/entity/store/*',
                     'metadataHref': 'https://api.moysklad.ru/api/remap/1.2/entity/store/metadata', 'type': 'store',
                     'mediaType': 'application/json',
                     'uuidHref': 'https://online.moysklad.ru/app/#warehouse/edit?id=*'}}
    else:
        store = {
            'meta': {'href': 'https://api.moysklad.ru/api/remap/1.2/entity/store/*',
                     'metadataHref': 'https://api.moysklad.ru/api/remap/1.2/entity/store/metadata', 'type': 'store',
                     'mediaType': 'application/json',
                     'uuidHref': 'https://online.moysklad.ru/app/#warehouse/edit?id=*'}}
    # корзина
    cart_count = 0
    cart_items = []
    total_cost = 0
    user_storage = Storage.objects.get(storage_name=user_city)

    # Текущая дата
    current_date = datetime.now()
    # Дата доставки (текущая дата + 4 дня)
    delivery_date = current_date + timedelta(days=4)
    # Дата доставки всего заказа изначальная
    order_delivery_date = None

    if request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first()
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            for item in cart_items:
                item.product.available_warehouses_count = Stock.objects.filter(product=item.product,
                                                                               quantity__gt=0).count()
                item.product.stocks = Stock.objects.filter(product=item.product)
                if user_storage:
                    item.is_available = Stock.objects.filter(product=item.product, warehouse=user_storage,
                                                             quantity__gt=0).exists()
                    if not item.is_available:
                        order_delivery_date = current_date + timedelta(days=4)
                else:
                    item.is_available = False

                item.stocks = Stock.objects.filter(product=item.product)
            cart_count = cart_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_cost = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        positions = []
        # Получение данных из формы
        phone = request.POST.get('phone')
        delivery_type = 'САМОВЫВОЗ' if request.POST.get('deliveryType') == 'pickup' else 'ДОСТАВКА'
        if delivery_type == 'САМОВЫВОЗ':
            city = request.POST.get('pickupShop')
            delivery_company = None
            delivery_price = 0
            delivery_info = f"{delivery_type}"
        elif delivery_type == 'ДОСТАВКА':
            city = request.POST.get('cityInput')
            print(request.POST.get('deliveryOption'))
            delivery_option = request.POST.get('deliveryOption').split(':')
            delivery_company = delivery_option[0]
            delivery_price = delivery_option[1]
            delivery_info = f"{delivery_type} / {delivery_company} / {delivery_price} руб."
            position = {
                "quantity": 1,
                "price": int(delivery_price) * 100,
                "assortment": {
                    "meta": {
                        "href": "https://api.moysklad.ru/api/remap/1.2/entity/serivce/a504a63d-a016-11ee-0a80-019900153ab9",
                        "type": "service",
                        "mediaType": "application/json"
                    }
                },
            }
            positions.append(position)
        else:
            delivery_info = 0
            city = 'город не указан'
            delivery_company = None
            delivery_price = 0
        name = request.POST.get('name')
        payment_type = request.POST.get('paymentType')

        # Создаем новый заказ
        new_order = Order()

        # Присваиваем значения полям заказа
        new_order.total_price = int(total_cost) + int(delivery_price)
        new_order.delivery_type = delivery_type
        new_order.delivery_price = delivery_price
        new_order.delivery_city = city
        new_order.phone = phone
        new_order.is_completed = False
        new_order.status = 'В обработке'

        # Сохраняем объект в базе данных
        new_order.save()

        new_order.number = 'ИМ-' + str(new_order.pk)

        # Добавление продуктов из корзины в заказ на мойсклад
        cart = Cart.objects.filter(session_key=request.session.session_key).first()
        cart_items = CartItem.objects.filter(cart=cart)

        for item in cart_items:
            position = {
                "quantity": item.quantity,
                "price": int(item.product.price) * 100,
                "assortment": {
                    "meta": {
                        "href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{item.product.moysklad_id}",
                        "type": "product",
                        "mediaType": "application/json"
                    }
                },
                "reserve": item.quantity
            }
            positions.append(position)

            OrderItem.objects.create(
                order=new_order,
                product=item.product,
                quantity=item.quantity
            )

        new_order.save()


        url = "https://api.moysklad.ru/api/remap/1.2/entity/customerorder"
        access_token = ""
        headers = {
            "Authorization": access_token,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json"
        }
        order_data = {
            "name": new_order.number,
            "description": new_order.delivery_city,
            "salesChannel": {
                "meta": {
                    'href': 'https://api.moysklad.ru/api/remap/1.2/entity/saleschannel/*',
                    'metadataHref': 'https://api.moysklad.ru/api/remap/1.2/entity/saleschannel/metadata',
                    'type': 'saleschannel',
                    'mediaType': 'application/json',
                    'uuidHref': 'https://online.moysklad.ru/app/#saleschannel/edit?id=*'}},
            "organization": {
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/*",
                    "type": "organization",
                    "mediaType": "application/json"
                }
            },
            "agent": {
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/*",
                    "type": "counterparty",
                    "mediaType": "application/json"
                }
            },
            "shipmentAddressFull": {
                "city": city,
                "addInfo": delivery_info,
                "comment": "Телефон клиента: " + phone,
            },
            "positions": positions

        }
        response = requests.post(url, json=order_data, headers=headers) #создаем заказ в мойсклад
        moysklad_id = response.json()['id']
        new_order.moysklad_id = moysklad_id
        new_order.save()

    context = {
        'city': user_city,
        'cart_items': cart_items,
        'cart_count': cart_count,
        'total_cost': int(total_cost),
        'delivery_date': delivery_date,
        'order_delivery_date': order_delivery_date,
    }
    return render(request, 'cart/order.html', context)
