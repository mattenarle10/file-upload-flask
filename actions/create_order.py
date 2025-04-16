import os
import psycopg2
from flask import url_for, flash, redirect, request, render_template
from db.mongodb.mongodb_connection import create_mongodb_connection

def process_order(request, app):
    """
    Process an order submission
    """
    try:
        # Get form data with validation
        product_id = request.form.get('product_id')
        if not product_id:
            flash('Product ID is required')
            return redirect(request.url)
            
        # Get customer name
        customer_name = request.form.get('customer_name', '').strip()
        if not customer_name:
            flash('Customer name is required')
            return redirect(request.url)
            
        # Safely convert order_quantity to integer
        try:
            order_quantity = int(request.form.get('order_quantity', 1))
            if order_quantity <= 0:
                flash('Order quantity must be positive')
                return redirect(request.url)
        except ValueError:
            flash('Invalid order quantity')
            return redirect(request.url)
            
        # Connect to PostgreSQL with error handling
        conn = psycopg2.connect(
            host=os.environ["POSTGRESQL_DB_HOST"],
            database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
            user=os.environ['POSTGRESQL_DB_USERNAME'],
            password=os.environ['POSTGRESQL_DB_PASSWORD']
        )
        conn.autocommit = False  # Start transaction mode
        cur = conn.cursor()
        
        try:
            # First check if there's enough stock
            cur.execute("SELECT name, stock_count FROM products WHERE id = %s", (product_id,))
            result = cur.fetchone()
            
            if not result:
                conn.rollback()
                cur.close()
                conn.close()
                flash('Product not found')
                return redirect(url_for('create_order'))
                
            product_name, current_stock = result
            
            if current_stock < order_quantity:
                conn.rollback()
                cur.close()
                conn.close()
                flash(f'Not enough stock available for {product_name}. Available: {current_stock}')
                return redirect(url_for('create_order'))
            
            # Calculate order total (simple example)
            unit_price = 10.00  # You might want to add a price column to products
            total = unit_price * order_quantity
            
            # Create order record - simplified without tax
            cur.execute("""
                INSERT INTO orders (customer_name, total, tax, pretax_amount) 
                VALUES (%s, %s, %s, %s) RETURNING id
                """, (customer_name, total, 0, total))  # Tax is 0, pretax_amount equals total
            
            order_id = cur.fetchone()[0]
            
            # Create stock movement record
            cur.execute("""
                INSERT INTO stock_movements (product_id, order_id, quantity) 
                VALUES (%s, %s, %s)
                """, (product_id, order_id, order_quantity))
            
            # Update product stock
            new_stock = current_stock - order_quantity
            cur.execute("UPDATE products SET stock_count = %s WHERE id = %s", 
                       (new_stock, product_id))
            
            # Commit the transaction
            conn.commit()
            
            flash(f'Order #{order_id} created successfully for {product_name}')
            
            # Close the current connection
            cur.close()
            conn.close()
            
            # Return to the GET part of the function to fetch fresh data
            return redirect(url_for('create_order'))
            
        except psycopg2.Error as e:
            conn.rollback()
            app.logger.error(f"Database error: {e}")
            flash(f'Error creating order: {str(e)}')
            return redirect(request.url)
        finally:
            if cur and not cur.closed:
                cur.close()
            if conn and not conn.closed:
                conn.close()
            
    except Exception as e:
        app.logger.error(f"Unexpected error in create_order: {e}")
        flash('An unexpected error occurred')
        return redirect(request.url)

def get_products_and_orders():
    """
    Get products and recent orders for the order page
    """
    try:
        conn = psycopg2.connect(
            host=os.environ["POSTGRESQL_DB_HOST"],
            database=os.environ["POSTGRESQL_DB_DATABASE_NAME"],
            user=os.environ['POSTGRESQL_DB_USERNAME'],
            password=os.environ['POSTGRESQL_DB_PASSWORD']
        )
        cur = conn.cursor()
        
        # Get all products with their details including MongoDB image ID
        cur.execute("""
            SELECT p.id, p.name, p.stock_count, p.image_mongodb_id 
            FROM products p
        """)
        products = cur.fetchall()
        
        # Get all images from MongoDB
        client, database, collection = create_mongodb_connection("file-uploads")
        all_images = list(collection.find({}))
        
        # Prepare data for template
        parsed_products = []
        
        # Process products with their images
        for product in products:
            product_id = product[0]
            product_name = product[1]
            stock_count = product[2]
            image_mongodb_id = product[3]
            
            # Find matching image for this product
            matching_image = None
            
            # Try to find by product_id in MongoDB
            for img in all_images:
                if 'product_id' in img and str(img['product_id']) == str(product_id):
                    matching_image = img
                    break
            
            # If no match by product_id, try by image_mongodb_id
            if not matching_image and image_mongodb_id:
                for img in all_images:
                    if '_id' in img and str(img['_id']) == image_mongodb_id:
                        matching_image = img
                        break
            
            # If we found a matching image
            if matching_image and 'file_path' in matching_image:
                img_url = url_for('download_file', name=matching_image['file_path'])
                
                product_data = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "stock_count": stock_count,
                    "image_url": img_url,
                    "file_path": matching_image['file_path']
                }
            else:
                # No matching image found
                product_data = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "stock_count": stock_count,
                    "image_url": "",
                    "file_path": ""
                }
            
            parsed_products.append(product_data)
        
        # Fetch recent orders for display
        orders = []
        try:
            # Get recent orders with product details through stock_movements
            cur.execute("""
                SELECT o.id, sm.product_id, p.name, sm.quantity, o.created_at, p.image_mongodb_id, o.total, o.customer_name 
                FROM orders o
                JOIN stock_movements sm ON o.id = sm.order_id
                JOIN products p ON sm.product_id = p.id
                ORDER BY o.created_at DESC
                LIMIT 10
            """)
            
            recent_orders = cur.fetchall()
            
            # Process orders with product images
            for order in recent_orders:
                order_id = order[0]
                product_id = order[1]
                product_name = order[2]
                quantity = order[3]
                order_date = order[4]
                image_mongodb_id = order[5]
                total = order[6]
                customer_name = order[7]
                
                # Find matching image for this product
                image_url = ""
                
                # Try to find by product_id in MongoDB
                for img in all_images:
                    if 'product_id' in img and str(img['product_id']) == str(product_id):
                        if 'file_path' in img:
                            image_url = url_for('download_file', name=img['file_path'])
                        break
                
                # If no match by product_id, try by image_mongodb_id
                if not image_url and image_mongodb_id:
                    for img in all_images:
                        if '_id' in img and str(img['_id']) == image_mongodb_id:
                            if 'file_path' in img:
                                image_url = url_for('download_file', name=img['file_path'])
                            break
                
                order_data = {
                    "order_id": order_id,
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": quantity,
                    "order_date": order_date,
                    "image_url": image_url,
                    "total": total,
                    "customer_name": customer_name
                }
                
                orders.append(order_data)
        except Exception as e:
            app.logger.error(f"Error fetching orders: {e}")
            # Continue without orders if there's an error
        
        client.close()
        cur.close()
        conn.close()
        
        return parsed_products, orders
        
    except Exception as e:
        app.logger.error(f"Error loading products: {e}")
        return [], []

def render_order_page(app):
    """
    Render the order page with products and recent orders
    """
    try:
        products, orders = get_products_and_orders()
        return render_template('create_order.html', products=products, orders=orders)
    except Exception as e:
        app.logger.error(f"Error loading products: {e}")
        flash('Error loading products')
        return render_template('create_order.html', products=[], orders=[])