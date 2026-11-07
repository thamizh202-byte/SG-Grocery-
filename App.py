import streamlit as st
import pandas as pd
from fpdf import FPDF
from PIL import Image
import google.generativeai as genai
import json
import sqlite3
from datetime import datetime

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & DATABASE SETUP (with GST column)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Supermarket Inventory & GST System",
    page_icon="🛒",
    layout="wide"
)

def init_db():
    conn = sqlite3.connect("supermarket.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            vendor_name TEXT,
            item_name TEXT,
            quantity INTEGER,
            unit_price REAL,
            subtotal REAL,
            gst_amount REAL,
            grand_total REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 2. AUTHENTICATION (LOGIN SYSTEM)
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

USER_CREDENTIALS = {
    "admin@supermarket.com": "admin123",
    "store@supermarket.com": "store2026"
}

def login_page():
    st.title("🔑 Supermarket System Login")
    st.subheader("உங்கள் மின்னஞ்சல் மற்றும் கடவுச்சொல்லைப் பயன்படுத்தி உள்நுழையவும்")
    
    with st.form("login_form"):
        email_input = st.text_input("Email ID / மின்னஞ்சல் முகவரி")
        password_input = st.text_input("Password / கடவுச்சொல்", type="password")
        submit_button = st.form_submit_button("Login / உள்நுழை")

        if submit_button:
            email_clean = email_input.strip().lower()
            if email_clean in USER_CREDENTIALS and USER_CREDENTIALS[email_clean] == password_input:
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email_clean
                st.success("வெற்றிகரமாக உள்நுழைந்துவிட்டீர்கள்!")
                st.rerun()
            else:
                st.error("தவறான Email அல்லது Password! மீண்டும் முயற்சிக்கவும்.")

def logout():
    st.session_state["authenticated"] = False
    st.session_state["user_email"] = None
    st.rerun()

# ---------------------------------------------------------
# 3. PDF GENERATION HELPER (with 9% GST breakdown)
# ---------------------------------------------------------
def create_vendor_pdf(vendor_name, items_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    pdf.cell(200, 10, txt=f"Purchase Order - {vendor_name}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="--------------------------------------------------", ln=True, align='C')
    pdf.ln(5)

    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(50, 10, "Item Name", border=1)
    pdf.cell(25, 10, "Qty", border=1)
    pdf.cell(30, 10, "Price ($)", border=1)
    pdf.cell(35, 10, "Subtotal ($)", border=1)
    pdf.cell(30, 10, "GST (9%)", border=1)
    pdf.cell(30, 10, "Total ($)", border=1)
    pdf.ln()

    # Table Content
    pdf.set_font("Arial", size=9)
    total_sub = 0.0
    total_gst = 0.0
    grand_total = 0.0

    for item in items_list:
        pdf.cell(50, 10, str(item['Item Name']), border=1)
        pdf.cell(25, 10, str(item['Quantity']), border=1)
        pdf.cell(30, 10, f"${item['Unit Price']:.2f}", border=1)
        pdf.cell(35, 10, f"${item['Subtotal']:.2f}", border=1)
        pdf.cell(30, 10, f"${item['GST']:.2f}", border=1)
        pdf.cell(30, 10, f"${item['Grand Total']:.2f}", border=1)
        pdf.ln()
        
        total_sub += item['Subtotal']
        total_gst += item['GST']
        grand_total += item['Grand Total']

    # Summary Row
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(140, 10, "Subtotal:", border=1)
    pdf.cell(60, 10, f"${total_sub:.2f}", border=1)
    pdf.ln()
    pdf.cell(140, 10, "Total GST (9%):", border=1)
    pdf.cell(60, 10, f"${total_gst:.2f}", border=1)
    pdf.ln()
    pdf.cell(140, 10, "Grand Total (incl. 9% GST):", border=1)
    pdf.cell(60, 10, f"${grand_total:.2f}", border=1)

    return pdf.output(dest='S').encode('latin-1')

# ---------------------------------------------------------
# 4. DATABASE HELPERS
# ---------------------------------------------------------
def save_to_db(user_email, items_list):
    conn = sqlite3.connect("supermarket.db")
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for item in items_list:
        cursor.execute("""
            INSERT INTO purchases (user_email, vendor_name, item_name, quantity, unit_price, subtotal, gst_amount, grand_total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_email, item['Vendor Name'], item['Item Name'], item['Quantity'], item['Unit Price'], item['Subtotal'], item['GST'], item['Grand Total'], current_time))
    
    conn.commit()
    conn.close()

def fetch_purchase_history():
    conn = sqlite3.connect("supermarket.db")
    df = pd.read_sql_query("SELECT * FROM purchases ORDER BY id DESC", conn)
    conn.close()
    return df

# ---------------------------------------------------------
# 5. MAIN APPLICATION (AFTER LOGIN)
# ---------------------------------------------------------
def main_app():
    user_email = st.session_state.get('user_email', '')
    st.sidebar.write(f"👤 Logged in as: **{user_email}**")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ OCR Settings")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="பில் போட்டோவை படிக்க API Key தேவை.")

    if st.sidebar.button("Logout / வெளியேறு"):
        logout()

    st.title("🛒 Supermarket Inventory, OCR & 9% GST Calculation")
    st.markdown("---")

    if "purchase_data" not in st.session_state:
        st.session_state["purchase_data"] = []

    # Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["📝 Manual Entry", "📷 AI Bill OCR & Current List", "📊 Purchase History"])

    with tab1:
        st.subheader("புதிய பொருளைக் கைமுறையாகச் சேர்க்கவும் (9% GST உட்பட)")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            vendor_name = st.text_input("Vendor Name (வெண்டார் பெயர்)", key="v_name")
        with col2:
            item_name = st.text_input("Item Name (பொருளின் பெயர்)", key="i_name")
        with col3:
            quantity = st.number_input("Quantity (எண்ணிக்கை)", min_value=1, value=1, key="qty")
        with col4:
            unit_price = st.number_input("Unit Price (ஒரு பொருளின் விலை $)", min_value=0.0, value=0.0, step=0.5, key="price")

        if st.button("➕ Add Item / சேர்க்கவும்"):
            if vendor_name.strip() == "" or item_name.strip() == "":
                st.warning("தயவுசெய்து Vendor Name மற்றும் Item Name இரண்டையும் உள்ளிடவும்.")
            else:
                subtotal = quantity * unit_price
                gst = subtotal * 0.09  # 9% GST Calculation
                grand_total = subtotal + gst

                st.session_state["purchase_data"].append({
                    "Vendor Name": vendor_name.strip(),
                    "Item Name": item_name.strip(),
                    "Quantity": quantity,
                    "Unit Price": unit_price,
                    "Subtotal": subtotal,
                    "GST": gst,
                    "Grand Total": grand_total
                })
                st.success(f"'{item_name}' (9% GST உடன் சேர்த்து) வெற்றிகரமாகச் சேர்க்கப்பட்டது!")

    with tab2:
        st.subheader("📷 பில் / ரசீது புகைப்படம் (Upload அல்லது Camera)")
        input_method = st.radio("புகைப்படத்தை எப்படி பெற விரும்புகிறீர்கள்?", ["📁 Upload File (பைல் அப்லோட்)", "📸 Take Picture (நேரடி கேமரா புகைப்படம்)"], key="ocr_method")
        
        image = None
        if input_method == "📁 Upload File (பைல் அப்லோட்)":
            uploaded_file = st.file_uploader("பில் படத்தின் வடிவமைப்பு (jpg, png)", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Bill", use_column_width=True)
        else:
            camera_image = st.camera_input("கேமரா மூலம் பில்லை போட்டோ எடுக்கவும்")
            if camera_image is not None:
                image = Image.open(camera_image)
                st.image(image, caption="Captured Bill from Camera", use_column_width=True)

        if image is not None:
            if st.button("🔍 Extract Details using AI (விவரங்களை எடு)"):
                if not gemini_api_key:
                    st.error("தயவுசெய்து Sidebar-ல் உங்கள் Gemini API Key-ஐ உள்ளிடவும்.")
                else:
                    with st.spinner("பில் விவரங்களை AI படித்துக் கொண்டிருக்கிறது..."):
                        try:
                            genai.configure(api_key=gemini_api_key)
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            
                            prompt = """
                            Analyze this purchase bill image and extract the items. 
                            Return ONLY a valid JSON array of objects with keys: 
                            "vendor_name" (string, name of the supplier/vendor), 
                            "item_name" (string), 
                            "quantity" (integer), 
                            "unit_price" (float). 
                            Do not include any markdown formatting like ```json, just return the raw JSON string or standard JSON array.
                            """
                            response = model.generate_content([image, prompt])
                            clean_text = response.text.replace("```json", "").replace("```", "").strip()
                            extracted_items = json.loads(clean_text)

                            for item in extracted_items:
                                v = item.get("vendor_name", "General Vendor")
                                i = item.get("item_name", "Unknown Item")
                                q = int(item.get("quantity", 1))
                                p = float(item.get("unit_price", 0.0))
                                
                                subtotal = q * p
                                gst = subtotal * 0.09
                                grand_total = subtotal + gst

                                st.session_state["purchase_data"].append({
                                    "Vendor Name": v,
                                    "Item Name": i,
                                    "Quantity": q,
                                    "Unit Price": p,
                                    "Subtotal": subtotal,
                                    "GST": gst,
                                    "Grand Total": grand_total
                                })
                            st.success("பில் விவரங்கள் மற்றும் 9% GST கணக்கீடு வெற்றிகரமாகச் சேர்க்கப்பட்டன!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"பிழை ஏற்பட்டது: {e}")

        st.markdown("---")
        # Display Current Items Table
        if st.session_state["purchase_data"]:
            st.subheader("📋 தற்போதைய பர்சேஸ் பட்டியல் & GST விவரங்கள்")
            df = pd.DataFrame(st.session_state["purchase_data"])
            st.dataframe(df, use_container_width=True)

            # Overall Summary Calculation
            total_sub_sum = df["Subtotal"].sum()
            total_gst_sum = df["GST"].sum()
            total_grand_sum = df["Grand Total"].sum()

            st.markdown(f"**💰 மொத்த விலை (Subtotal):** ${total_sub_sum:.2f} | **🏛️ மொத்த GST (9%):** ${total_gst_sum:.2f} | **💵 இறுதி மொத்தத் தொகை (Grand Total):** **${total_grand_sum:.2f}**")
            st.markdown("---")

            col_left, col_right = st.columns([1, 1])

            with col_left:
                if st.button("🗑️ Clear All / அனைத்தையும் நீக்கு"):
                    st.session_state["purchase_data"] = []
                    st.rerun()

            with col_right:
                if st.button("🏁 Finish & Save to Database & PDFs"):
                    save_to_db(user_email, st.session_state["purchase_data"])
                    
                    vendor_groups = {}
                    for item in st.session_state["purchase_data"]:
                        v = item["Vendor Name"]
                        if v not in vendor_groups:
                            vendor_groups[v] = []
                        vendor_groups[v].append(item)

                    st.success("✅ டேட்டாபேஸில் 9% GST விவரங்களுடன் வெற்றிகரமாக சேமிக்கப்பட்டன!")
                    st.subheader("📄 Vendor-Wise PDFs Generated Successfully!")

                    for v_name, items in vendor_groups.items():
                        pdf_bytes = create_vendor_pdf(v_name, items)
                        st.download_button(
                            label=f"⬇️ Download PDF for {v_name}",
                            data=pdf_bytes,
                            file_name=f"Purchase_Order_{v_name}.pdf",
                            mime="application/pdf"
                        )
        else:
            st.info("இன்னும் பொருள்கள் எதுவும் சேர்க்கப்படவில்லை.")

    with tab3:
        st.subheader("📊 பர்சேஸ் வரலாறு & GST கணக்கீட்டுப் பதிவுகள் (Database History)")
        history_df = fetch_purchase_history()
        
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True)
            
            csv_data = history_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Full History as CSV",
                data=csv_data,
                file_name="supermarket_purchase_history_with_gst.csv",
                mime="text/csv"
            )
        else:
            st.info("டேட்டாபேஸில் எந்த வரலாறும் இல்லை.")

# ---------------------------------------------------------
# 6. EXECUTION ROUTER
# ---------------------------------------------------------
if not st.session_state["authenticated"]:
    login_page()
else:
    main_app()
