# อ่านก่อนพรีเซนต์

ใช้ CMZ_Phase2_Automatic_15slides_v2.pptx หรือ PDF ชื่อเดียวกัน มี15หน้า ไม่มีหน้า Next evidence needed แยก

เปิด OPEN_THIS_FIRST.md ในหน้าแรกGitHubไว้กดหลักฐาน และใช้ PRESENTATION_QA.md ซ้อมตอบ อังกฤษสั้นพร้อมไทย

ผลหลักคือ53Walking 9Feeding 286Unknown จาก348จุดเวลา ไม่ใช่ระยะเวลาเดิน/กินทั้งวัน รอบเพิ่ม77ช่วงเป็นชุดแยก ไม่บวกกับผลหลัก

ทดลองภาพ12ภาพ threshold0.4:input640พบ1ภาพ,input1280พบ9ภาพ,CLAHE1280พบ8ภาพ,gamma1280พบ9ภาพ ภาพauditมีกรอบROIเดิม จึงไม่ใช่หลักฐานว่าaccuracyเพิ่ม

มีต้นแบบที่ฝึกแล้ว ผลรันจริง และหลักฐานตรวจโค้ด แต่ Inactiveที่ยืนยันและaccuracyจากชุดทดสอบอิสระยังไม่มี ห้ามใช้unit testหรือ60%development recoveryแทนaccuracyทั้งระบบ

Workbookชื่อHistoricalเก็บผลหลักเดิมโดยไม่แก้ไข ผลใหม่อยู่ในauto_evidenceและenhancement
