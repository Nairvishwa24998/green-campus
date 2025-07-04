from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import select

from app import db, logger
from app.forms import AddProductForm, DeleteForm, EditProductForm
from app.models import Inventory

# === Blueprint Setup ===
vendors_bp = Blueprint('vendors', __name__)


# === Route: Landing Page for Smart Food Expiry System ===
@vendors_bp.route('/smart_food_expiry', methods=['GET', 'POST'])
@login_required
def smart_food_expiry():
    """
    Shows the main product upload form for vendors.
    """
    add_product_form = AddProductForm()
    return render_template('smart_food_expiry.html',
                           title='Smart Food Expiry System',
                           add_product_form=add_product_form,
                           confetti=False)


# === Route: View Vendor's Current Inventory ===
@vendors_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    """
    Displays the vendor's uploaded products with options to add, edit, or delete.
    """
    delete_product_form = DeleteForm()
    add_product_form = AddProductForm()
    edit_product_form = EditProductForm()
    view = request.args.get("view")
    show_form = request.args.get("show_form", "false") == "true"
    show_confetti = session.pop('show_confetti', False)
    user_products_list = get_user_products(current_user.id)

    return render_template('inventory.html',
                           title='Current Inventory',
                           user_products_list=user_products_list,
                           confetti=show_confetti,
                           delete_product_form=delete_product_form,
                           edit_product_form=edit_product_form,
                           add_product_form=add_product_form,
                           view=view,
                           show_form=show_form)


# === Route: Add Product to Inventory ===
@vendors_bp.route('/add_product', methods=['POST'])
@login_required
def add_product():
    """
    Adds a new product or updates quantity if it already exists.
    """
    add_product_form = AddProductForm()
    if add_product_form.validate_on_submit():
        product_name = add_product_form.name.data
        product_expiry_date = add_product_form.expiry_date.data
        product_units = add_product_form.units.data
        product_category = add_product_form.category.data
        product_price = add_product_form.price.data
        product_location = add_product_form.location.data

        product_discount = (add_product_form.discount.data or 0) / 100
        final_price = round(product_price * (1 - product_discount), 2)

        inventory_product = Inventory(
            name=product_name,
            expiry_date=product_expiry_date,
            units=product_units,
            category=product_category,
            marked_price=product_price,
            discount=product_discount,
            final_price=final_price,
            location=product_location,
            user_id=current_user.id
        )

        # Avoid duplicate entry by checking name match
        existing_product = db.session.scalars(select(Inventory).filter_by(name=product_name)).first()

        if existing_product is None:
            db.session.add(inventory_product)
        else:
            existing_product.units += product_units

        db.session.commit()
        flash("Product added successfully!", "success")
        session['show_confetti'] = True
        return redirect(url_for('vendors.inventory'))

    flash("Failed to add product. Please check the form.", "danger")
    return redirect(url_for('vendors.smart_food_expiry'))


# === Route: Delete Product from Inventory ===
@vendors_bp.route('/delete_product', methods=['POST'])
@login_required
def delete_product():
    """
    Deletes a product from the vendor's inventory.
    """
    delete_product_form = DeleteForm()
    if delete_product_form.validate_on_submit():
        product_id = delete_product_form.delete_product.data
        product = db.session.get(Inventory, product_id)
        if product:
            logger.debug(f"Deleting product: {product.name} (ID: {product.id})")
            db.session.delete(product)
            db.session.commit()

            # Confirm deletion
            deleted_product = db.session.get(Inventory, product_id)
            if deleted_product is None:
                flash(f'{product.name} successfully deleted', 'success')
            else:
                flash('Failed to delete product.', 'danger')
        else:
            flash('Product not found.', 'danger')

    return redirect(url_for('vendors.inventory'))


# === Route: Edit Product Information ===
@vendors_bp.route('/edit_product', methods=['GET', 'POST'])
@login_required
def edit_product():
    """
    Loads form with product details for editing and saves changes.
    """
    edit_product_form = EditProductForm()
    view = request.args.get("view")

    # Handle GET: populate form
    if request.method == 'GET':
        product_id = request.args.get('product_id')
        if product_id:
            product = db.session.get(Inventory, product_id)
            if product:
                populate_edit_form(product, edit_product_form)
            else:
                flash('Product not found.', 'danger')
                return redirect(url_for('vendors.inventory', view=view))

    # Handle POST: update DB
    if request.method == 'POST' and edit_product_form.validate_on_submit():
        product_id = edit_product_form.product_id.data
        product = db.session.get(Inventory, product_id)
        if product:
            update_product_fields(product, edit_product_form)
            db.session.commit()
            flash("Product updated successfully!", "success")
            session['show_confetti'] = True
        else:
            flash('Product not found.', 'danger')
        return redirect(url_for('vendors.inventory', view=view))

    # Fallback: re-render inventory with populated form
    user_products_list = get_user_products(current_user.id)
    return render_template('inventory.html',
                           title='Edit Product',
                           add_product_form=AddProductForm(),
                           edit_product_form=edit_product_form,
                           user_products_list=user_products_list,
                           delete_product_form=DeleteForm(),
                           show_form=True,
                           confetti=session.pop('show_confetti', False),
                           view=view)


# === Helper: Get All Products for a Vendor ===
def get_user_products(user_id):
    return list(db.session.scalars(select(Inventory).filter_by(user_id=user_id)))


# === Helper: Fill Edit Form with Existing Product Data ===
def populate_edit_form(product, form):
    form.product_id.data = product.id
    form.name.data = product.name
    form.expiry_date.data = product.expiry_date
    form.units.data = product.units
    form.price.data = product.marked_price
    form.location.data = product.location


# === Helper: Save Updated Product Fields to the Database ===
def update_product_fields(product, form):
    product.name = form.name.data
    product.expiry_date = form.expiry_date.data
    product.units = form.units.data
    product.marked_price = form.price.data
    product.location = form.location.data
    product.final_price = form.price.data  # This might need recalculating with discount
