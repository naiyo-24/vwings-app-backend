import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def generate_commission_slip_pdf(commission_data: dict, file_path: str):
    # commission_data needs: counsellor_name, counsellor_id, month, year, admitted_students, commission_per_student, total_commission, payment_mode, transaction_id
    
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
    
    elements.append(Paragraph("VWings24x7 Counsellor Commission Slip", title_style))
    elements.append(Spacer(1, 10))
    
    # Details section
    details = [
        ["Counsellor Name:", commission_data.get("counsellor_name", ""), "Counsellor ID:", commission_data.get("counsellor_id", "")],
        ["Month:", str(commission_data.get("month", "")), "Year:", str(commission_data.get("year", ""))],
        ["Payment Mode:", commission_data.get("payment_mode", "NEFT"), "Transaction ID:", commission_data.get("transaction_id", "") or "N/A"]
    ]
    
    detail_table = Table(details, colWidths=[100, 150, 100, 150])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 20))
    
    # Commission Breakdown
    breakdown = [
        ["Description", "Amount (INR)"],
        [f"Commission ( {commission_data.get('admitted_students', 0)} students @ {commission_data.get('commission_per_student', 0.0)} each )", f"{commission_data.get('total_commission', 0.0):.2f}"],
        ["Total Payout", f"{commission_data.get('total_commission', 0.0):.2f}"]
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
    
    doc.build(elements)

def generate_payout_slip_pdf(payout_data: dict, file_path: str):
    # payout_data needs: counsellor_name, counsellor_id, payout_no, payment_method, reference_no, date, amount
    
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
    
    elements.append(Paragraph("VWings24x7 Counsellor Payout Slip", title_style))
    elements.append(Spacer(1, 10))
    
    details = [
        ["Counsellor Name:", payout_data.get("counsellor_name", ""), "Counsellor ID:", payout_data.get("counsellor_id", "")],
        ["Payout No:", payout_data.get("payout_no", ""), "Date:", payout_data.get("date", "")],
        ["Payment Mode:", payout_data.get("payment_method", "Bank Transfer"), "Transaction ID:", payout_data.get("reference_no", "") or "N/A"]
    ]
    
    detail_table = Table(details, colWidths=[100, 150, 100, 150])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 20))
    
    breakdown = [
        ["Description", "Amount (INR)"],
        ["Total Earned Commissions", f"{payout_data.get('amount', 0.0):.2f}"],
        ["Total Payout", f"{payout_data.get('amount', 0.0):.2f}"]
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
