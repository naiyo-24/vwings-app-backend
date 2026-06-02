import re

path = r"d:\VWings24x7-Admin-App\src\pages\Commissions.jsx"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update handleSubmit
handle_submit_old = """  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData, slipFile, calcData);
  };"""
  
handle_submit_new = """  const handleSubmit = (e) => {
    e.preventDefault();
    if (!calcData) {
      alert("Please wait for calculation to finish.");
      return;
    }
    const dataToSave = {
      counsellor_id: formData.counsellor_id,
      month: parseInt(formData.month),
      year: parseInt(formData.year),
      admitted_students: calcData.admitted_students,
      commission_per_student: calcData.commission_per_student,
      total_commission: calcData.total_commission,
      transaction_id: formData.transaction_id || `TXN_${Date.now()}`
    };
    onSave(dataToSave, slipFile);
  };"""

content = content.replace(handle_submit_old, handle_submit_new)

# 2. Add transaction_id input
input_old = """              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Payout Slip (PDF/Image) (Optional)</label>
                <input type="file" onChange={(e) => setSlipFile(e.target.files[0])} style={{ background: 'var(--surface)', padding: '10px' }} />
              </div>"""

input_new = """              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>NEFT Transaction ID *</label>
                <input type="text" name="transaction_id" value={formData.transaction_id || ''} onChange={handleChange} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px 16px', color: 'var(--text-main)' }} required />
              </div>

              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Payout Slip (PDF/Image) (Optional)</label>
                <input type="file" onChange={(e) => setSlipFile(e.target.files[0])} style={{ background: 'var(--surface)', padding: '10px' }} />
              </div>"""

content = content.replace(input_old, input_new)

# 3. Update handleSave
save_old_regex = r"const handleSave = async \(data, slipFile, calcData\) => \{[\s\S]*?alert\('Failed to save payout\. Check console\.'\);\s*\n\s*\}\s*\n\s*\};\s*"
save_new = """const handleSave = async (data, slipFile) => {
    try {
      let response;
      if (slipFile) {
        const formData = new FormData();
        formData.append('counsellor_id', data.counsellor_id);
        formData.append('month', data.month);
        formData.append('year', data.year);
        formData.append('file', slipFile);
        formData.append('admitted_students', data.admitted_students);
        formData.append('per_student_commission', data.commission_per_student);
        formData.append('total_amount', data.total_commission);
        
        response = await fetch(`${API_BASE_URL}/api/commissions/create`, {
          method: 'POST',
          body: formData
        });
      } else {
        response = await fetch(`${API_BASE_URL}/api/commissions/calculate-and-pay`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
      }

      if (response.ok) {
        setModalMode(false);
        fetchData();
      } else {
        const errData = await response.json();
        alert(`Failed to upload: ${errData.detail}`);
      }
    } catch (err) {
      console.error('Error uploading payout slip:', err);
      alert('Failed to save payout. Check console.');
    }
  };
"""

content = re.sub(save_old_regex, save_new, content)

# 4. update calculate & pay button text
btn_old = """<button type="submit" form="commission-form" className="btn-primary">Save Payout</button>"""
btn_new = """<button type="submit" form="commission-form" className="btn-primary" disabled={loadingCalc}>Calculate & Pay</button>"""
content = content.replace(btn_old, btn_new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated Commissions.jsx")
