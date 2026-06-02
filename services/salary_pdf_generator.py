import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def generate_salary_slip_pdf(salary_data: dict, file_path: str):
    # salary_data needs: teacher_name, teacher_id, month, year, fixed_salary, commission_per_student, referrals_admitted, total_salary, payment_mode, transaction_id
    
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', 
        parent=styles['Heading1'], 
        alignment=TA_CENTER,
        textColor=colors.HexColor("#000000"),
        spaceAfter=20
    )
    
    elements.append(Paragraph("VWings24x7 Teacher Salary Slip", title_style))
    elements.append(Spacer(1, 10))
    
    # Details section
    details = [
        ["Teacher Name:", salary_data.get("teacher_name", ""), "Teacher ID:", salary_data.get("teacher_id", "")],
        ["Month:", str(salary_data.get("month", "")), "Year:", str(salary_data.get("year", ""))],
        ["Payment Mode:", salary_data.get("payment_mode", ""), "Transaction ID:", salary_data.get("transaction_id", "") or "N/A"]
    ]
    
    detail_table = Table(details, colWidths=[100, 150, 100, 150])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 20))
    
    # Salary Breakdown
    breakdown = [
        ["Description", "Amount (INR)"],
        ["Fixed Salary", f"{salary_data.get('fixed_salary', 0.0):.2f}"],
        [f"Commission ( {salary_data.get('referrals_admitted', 0)} referrals @ {salary_data.get('commission_per_student', 0.0)} each )", f"{salary_data.get('commission_per_student', 0.0) * salary_data.get('referrals_admitted', 0):.2f}"],
        ["Total Salary", f"{salary_data.get('total_salary', 0.0):.2f}"]
    ]
    
    breakdown_table = Table(breakdown, colWidths=[300, 150])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#333333")),
        ('TEXTCOLOR', (0,0), (1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f9f9f9")),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    
    elements.append(breakdown_table)
    
    # Build PDF
    doc.build(elements)
