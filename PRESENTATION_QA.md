# CMZ presentation questions and short answers

Use [OPEN_THIS_FIRST.md](OPEN_THIS_FIRST.md) to open the matching evidence. The English line is ready to say. Thai text explains its meaning.

## 1. What is the project about?

**We use CCTV video to propose the civet's visible behavior and summarize the sampled results.**

เราใช้วิดีโอ CCTV เสนอพฤติกรรมที่เห็น และสรุปผลจากช่วงตัวอย่าง ยังไม่ได้ยืนยันพฤติกรรมทุกวินาที

## 2. What did you train yourself?

**We trained a Random Forest for Walking and Feeding. MegaDetector is a separate pretrained animal detector.**

เราฝึกตัวจำแนกพฤติกรรม RF เอง ส่วน MD ใช้น้ำหนักที่ฝึกมาแล้ว ไม่ได้อ้างว่าฝึก YOLO ชะมดใหม่

Open: [training report](submission/2026-11-01/historical_results/BATCH_TRAINING_REPORT.json).

## 3. Why use Random Forest?

**Our labeled dataset is small. Random Forest can use simple motion features without training a large video network. The small dataset still limits generalization.**

ข้อมูลติดป้ายมีน้อย จึงใช้ฟีเจอร์การเคลื่อนไหวกับ RF แต่ไม่ได้แปลว่าโมเดลจะใช้ได้แม่นกับทุกสถานการณ์

## 4. How much training data?

**Nine reviewed clips provide 74 seconds: 60 seconds Feeding and 14 seconds Walking. We divide them into 37 two-second segments. These segments are not independent events.**

9 คลิป รวม 74 วินาที แบ่งเป็น 37 ช่วง ไม่ใช่ 37 คลิปอิสระ

Open: [annotation register](submission/2026-11-01/ANNOTATION_REGISTER.csv).

## 5. What are the 18 features?

**We calculate six motion and frame-difference measures. For each measure, we take the mean, standard deviation and 90th percentile. Six times three gives 18 features.**

6 ค่าการเคลื่อนไหว สรุปค่าละ 3 แบบ รวม 18 ฟีเจอร์ ใช้ภาพเทาเต็มเฟรม 96×96

## 6. What is a window?

**A window is a short video interval. The historical analysis uses two seconds per window, sampled once within each five-minute interval.**

window คือช่วงคลิปสั้น ๆ รอบหลักเลือกช่วงละ 2 วินาทีภายในแต่ละ 5 นาที ไม่ได้วิเคราะห์ครบทั้ง 5 นาที

## 7. Did you analyze every video?

**The historical sampling plan includes all 31 discovered videos. It samples short intervals, not every second of every recording.**

ครบทุกไฟล์ในแผนสุ่ม แต่ไม่ครบทุกวินาที

Open: [per-video coverage](submission/2026-11-01/historical_results/PER_VIDEO_SAMPLING_TABLE.csv).

## 8. Why are there 1,319 windows but only 348 points?

**Several cameras record the same time. The 1,319 camera windows become 348 nominal time points when matching camera views are combined.**

มีกล้องถ่ายเวลาเดียวกัน จึงรวมให้เป็นจุดเวลาเดียว ไม่บวกเวลาสัตว์ซ้ำ

## 9. What are the main results?

**Among 348 fused sample points, the model proposes Walking at 53, Feeding at 9, and Unknown at 286. These are model proposals, not verified full-day durations.**

จำนวนจุดตัวอย่างที่ทำนาย ไม่ใช่นาทีเดินหรือกินทั้งวัน

Open: [fused results](submission/2026-11-01/historical_results/FUSED_SAMPLED_TIMES.csv).

## 10. Where is Inactive?

**Verified Inactive is unavailable in this pilot. We do not have an independently evaluated Resting or Sleeping class, and we do not count Unknown as Inactive.**

ยังไม่มีผล Inactive ที่ยืนยันได้ ต้องตอบตรง ๆ การตรวจจับไม่พบตัวแทนการพักไม่ได้

## 11. What does possible shelter mean?

**At 198 nominal times, all four cameras supplied decoded windows without endpoint animal proposals. We report possible shelter under a clock-alignment assumption. Detector misses can cause the same result.**

เป็นสมมติฐานอาจอยู่ในที่หลบ ไม่ใช่ตรวจพบว่าหลับ และตรวจไม่พบก็อาจเป็น MD พลาด

## 12. How accurate is it?

**We do not have independent multi-class accuracy yet. The 18 out of 30 seconds, or 60%, is recovery on previously exposed Walking development clips. It is not overall accuracy.**

อย่าใช้ 60% เป็น accuracy ทั้งระบบ และอย่าเอา 96.3% จากเฟส 1 มาตอบแทน

Open: [development replay](submission/2026-11-01/preflight_evidence/REPLAY_WALKING_CHECKS.json).

## 13. Show me your tests

**We can show software tests, data-integrity checks and development replays separately. Software tests check the implementation. They do not prove behavior accuracy.**

ถามว่าเทสส่วนไหน แล้วกดลิงก์ให้ตรง ถ้าถาม accuracy ต้องตอบข้อ 12 ไม่เปิดจำนวน unit test แทน

Open: [software log](submission/2026-11-01/SOFTWARE_TESTS.txt) · [table verification](submission/2026-11-01/INTEGRITY_CHECK.json) · [replay](submission/2026-11-01/preflight_evidence/REPLAY_WALKING_CHECKS.json).

## 14. Why so much Unknown?

**The animal can be hidden, missed by the detector, unclear, or outside the trained behavior classes. We preserve uncertainty rather than assigning an unsupported behavior.**

ตัวอาจถูกบัง MD พลาด ภาพไม่ชัด หรือพฤติกรรมไม่อยู่ในคลาสที่ฝึก

## 15. Does YOLO detect Feeding?

**No. MegaDetector proposes animal presence. The Random Forest proposes behavior from motion features. Stillness near a bowl alone does not confirm eating.**

MD ตรวจตัวสัตว์ RF เสนอพฤติกรรม และอยู่นิ่งข้างชามยังไม่ยืนยันว่ากิน

## 16. Did image improvement help?

**We compared raw frames, a larger detector input, CLAHE and gamma correction on the same fixed images. The paired table shows how proposal counts change. The saved audit images already contain ROI outlines, so this is an exploratory check, not proof of better accuracy on clean originals.**

ชี้ตารางผลทดลองจริง แยกเรื่องตรวจพบเพิ่มออกจากเรื่องถูกต้องเพิ่ม ไม่บอกว่าแม่นขึ้นเพียงเพราะคะแนนสูงขึ้น

Open: [enhancement results](submission/2026-11-01/enhancement/ENHANCEMENT_SUMMARY.csv).

## 17. Can the position heatmap show its favorite room?

**No. This plot counts detected image positions in sampled frames. Camera views can overlap rooms, and the sample is not a validated room-occupancy study.**

เป็นตำแหน่งในภาพจากการตรวจจับ ไม่ใช่สรุปว่าสัตว์ชอบห้องไหน

## 18. Did you keep the Phase 1 plan?

**We kept the problem, behavior definitions and visibility distinction. The implementation now uses a pretrained detector and a trained classifier. Some planned outputs, such as validated rest and continuous room use, are not established.**

โครงเดิมยังอยู่ แต่วิธีทำเปลี่ยน และต้องแยกแผนเดิมออกจากของที่รันได้จริง

## 19. Can someone reproduce it?

**The repository includes source code, settings, annotation provenance, raw result tables and a saved reconstructed pilot model. The guide links each claim to its evidence. Original video access follows the source Drive permissions.**

มีโค้ด ตั้งค่า ผลดิบ ที่มาป้ายกำกับ และโมเดลที่ฝึกซ้ำจากคลิปตรวจเดิม แยกจากโมเดลเก่าที่ไม่ได้อยู่ในชุดส่ง

## 20. Is every requirement fully met?

**We demonstrate training, model explanation and traceable automatic outputs. Active/Inactive evaluation is partial because verified Inactive and independent behavior metrics are unavailable.**

หัวข้อส่งมีหลักฐานให้ตรวจ แต่ยังอ้างว่าระบบครบทุกพฤติกรรมและประเมินผ่านทั้งหมดไม่ได้

Open: [requirements map](submission/2026-11-01/REQUIREMENTS_TRACE.csv).

## 21. Why did the additional pass produce only Unknown?

**It is a separate control pass on compressed audit clips and one extra video, using a smaller detector input. In the paired image experiment, 1280 input produced more animal proposals than 640. The historical original-video totals are kept separate.**

รอบเพิ่มเป็นการทดลองอีกชุด ไม่ใช่รอบผลหลัก ภาพ audit ผ่านการย่อ/บีบอัด และ input เล็กทำให้ตรวจพลาดได้ ผลหลัก 53/9/286 ไม่ได้ถูกแทนด้วยรอบทดลองนี้
