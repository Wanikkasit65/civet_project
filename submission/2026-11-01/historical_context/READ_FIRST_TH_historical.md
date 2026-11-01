# CMZ Phase 2 — ผลรันจริงและแนวทางนำเสนอ

รอบ fast5m_20261101_112605_c33161 จบสถานะ complete: วิเคราะห์ตัวอย่างจากวิดีโอ 31/31 ไฟล์ กล้อง A01–A04 จำนวน 1,319 ช่วง ช่วงละ 2 วินาที โดยเลือกหนึ่งช่วงภายในแต่ละช่วงเวลา 5 นาที ไม่ใช่วิเคราะห์ทุกวินาทีของวิดีโอทั้งหมด ใช้ประมวลผลรอบนี้ประมาณ 23 นาที 21 วินาที ไม่รวมติดตั้งและพัฒนาระบบ

## อ่านไฟล์ตามนี้

1. เปิด CMZ_Phase2_Results.xlsx ดู Summary ก่อน ตารางอื่นเก็บแหล่งข้อมูลที่ตรวจย้อนกลับได้
2. เปิด CMZ_Phase2_Final.pptx ใช้นำเสนอผลจริงรอบนี้ ใช้ PDF หากเครื่องเปิด PowerPoint ไม่ได้
3. อ่านตารางเทียบโจทย์และสไลด์เดิมด้านล่างก่อนพูด ไม่ต้องรันวิดีโอใหม่เพื่อใช้ชุดผลนี้
4. โค้ดอยู่บน branch phase2/behavior-pilot-and-tables ของ GitHub (ลิงก์ด้านล่าง) ไม่ใช่ main ที่ merge แล้ว

## ตัวเลขหลักและความหมาย

วิดีโอต้นทางรวม 109.841925 camera-hours ซึ่งมีหลายกล้องถ่ายเวลาซ้อนกัน ห้ามเรียกว่าเวลาของสัตว์ 109.84 ชั่วโมง กลุ่มตัวอย่างรวม 2,638 camera-seconds เท่านั้น เมื่อรวมจุดเวลาที่ตรงกันตามเวลาชื่อไฟล์ เหลือ 348 nominal sample times โดย 310 จุดมีครบสี่กล้อง และ 38 จุดมีบางกล้อง นาฬิกาตรวจเพียงบางจุด ยังไม่ได้รับรองตลอดทุกไฟล์

| ผลที่รายงาน | จำนวนจุด | ร้อยละของ 348 จุด | การตีความ |
|---|---:|---:|---|
| Walking proposal | 53 | 15.23% | โมเดลเสนอว่าเดิน ยังไม่ใช่ข้อสังเกตที่คนยืนยันทุกจุด |
| Feeding proposal | 9 | 2.59% | โมเดลเสนอว่ากิน ตัวอย่างภาพยังยืนยันการกินโดยตรงได้ไม่ชัด |
| Unknown: conditional possible shelter | 198 | 56.90% | ไม่พบ animal proposal ที่ปลายช่วงทั้งสองในครบสี่กล้อง ณ nominal time เดียวกัน อาจอยู่ในกล่องภายใต้สมมติฐานนาฬิกาตรงกัน |
| Unknown: other | 88 | 25.29% | หลักฐานไม่พอ รวมกรณีกล้องไม่ครบและการตรวจไม่ชัด |
| รวม | 348 | 100.00% | สัดส่วนจุดตัวอย่าง ไม่ใช่สัดส่วนเวลาจริงทั้งวัน |

Active model proposals = 53 + 9 = 62/348 = 17.82%; Unknown รวม 286/348 = 82.18% ส่วน Inactive ที่ยืนยันจริงเป็น N/A เพราะไม่มีโมเดล Resting/Sleeping ที่ฝึกและประเมินแล้ว ห้ามใส่ 0 หรือใช้ 198 จุดแทนการนอนจริง ช่วงที่ไม่พบตัวอาจเป็น detector miss ได้ด้วย

ผลต่อกล้อง 1,319 แถวมี Walking 53, Feeding 10, Unknown 1,256 ต่างจากตารางรวมเวลาเพราะมีมุมกล้องซ้ำ ณ เวลาเดียวกัน จึงต้องใช้ตัวหารให้ถูก

## ตอบโจทย์อาจารย์อย่างไร

| โจทย์เดิม | หลักฐานที่มีจริง | ข้อจำกัดที่ต้องบอก |
|---|---|---|
| Train selected suitable data | ฝึก Random Forest จาก 9 ช่วงที่คนยืนยันเนื้อหาคลิป: Feeding 6 ช่วง รวม 60 วินาที; Walking 3 ช่วง รวม 14 วินาที แบ่งเป็น 37 ช่วงฝึก 2 วินาที (30 Feeding, 7 Walking) | เป็น pilot ข้อมูลน้อยและใกล้กันใน recording เดียว ไม่ครอบคลุมพัก/นอน และเวลาอ้างอิงต้นฉบับเดิมยังต้องตรวจ mapping |
| Explain selected AI/image model | Pretrained MegaDetector V5A ตรวจสัตว์; Farneback optical flow และ frame difference สรุป 18 features; Random Forest 200 trees แยก Walking/Feeding; ข้อมูลไม่พอเป็น Unknown | MegaDetector ไม่ได้ฝึกใหม่เป็น detector ชะมดโดยเฉพาะ; RF score ไม่ใช่ calibrated confidence |
| Design and evaluate output: Active/Inactive table or visualization | มี Summary, ตารางรายไฟล์/รายชั่วโมง, กราฟผลทำนายและ Unknown พร้อมแหล่งเวลา; มีการตรวจการทำงานและทบทวนตัวอย่างภาพ | มี Active proposals แต่ยังไม่มี observed Inactive ที่รองรับ; ไม่อ้าง activity budget ทั้งวัน |
| Evaluate system | ประมวลผลครบ 31 ไฟล์ในแผนสุ่ม, 1,319/1,319 sampled windows, ไม่มี decode error ใน sampled windows; development diagnostics และ qualitative audit | ไม่ใช่การทดสอบอิสระ: accuracy/precision/recall/F1 ของทุกพฤติกรรมยัง N/A โดยเฉพาะ Feeding ต้องตรวจเพิ่ม |
| GitHub / annotation link | repository และ branch ที่เผยแพร่โค้ดจริงด้านล่าง; ANNOTATION_REGISTER.csv ในชุดส่งมี 9 annotation พร้อม provenance | annotation register รักษา source offset เดิมไว้และระบุข้อจำกัด ไม่อ้างว่าแก้เวลาแล้ว; ไม่เผยแพร่วิดีโอโดยอัตโนมัติ |

เราเตรียมสิ่งส่งตามหัวข้อได้ แต่ต้องนำเสนอว่าเป็นต้นแบบจำแนกเดิน/กินพร้อม Unknown ไม่ใช่ระบบตรวจทุกพฤติกรรมที่แม่นยำผ่านการทดสอบอิสระแล้ว หากอาจารย์ต้องการ observed Inactive และ accuracy test โดยตรง สองข้อนี้ยังเป็นช่องว่างที่ต้องทำต่อ ห้ามเติมตัวเลขขึ้นเอง

## เทียบกับสไลด์เก่า

ตรวจ CMZ Project Phase 1 – Civet Behavior Monitoring.pptx.pptx (19 slides) และ CMZ_Phase2_Content_v2.pptx (13 slides) จากไฟล์เดิมแล้ว ตัวเลขข้างล่างเป็นข้อความที่อยู่ในสไลด์ ไม่ใช่ข้อมูลที่ยืนยันจาก CSV รอบนี้

| เรื่อง | สไลด์เดิม | ผลรอบปัจจุบัน / สิ่งที่ควรแก้ |
|---|---|---|
| ข้อมูล | Phase 1 slide 5: 22 คลิป 17m32s; slides 6/8: 537 observations | รอบนี้ 31 long videos; 1,319 sampled camera windows; 348 nominal times เป็นคนละชุด/คนละหน่วย ห้ามนำจำนวนมารวม |
| พฤติกรรม | Phase 1 slide 6: Walk80, Climb6, Eat93, Rest265, Other39, Not identifiable54 | ไม่มี annotation 537 แถวที่ตรวจซ้ำได้ในหลักฐานผลรอบนี้ ผู้ใช้แจ้งว่าข้อมูลเดิม AI mock จึงไม่ใช้เป็น ground truth หรือผลทดลองใหม่ |
| ความแม่นยำ | Phase 1 slide 14: 96.3%, 465/483 | ผลปัจจุบัน evaluation=null และ whole_period_behavior_accuracy=null ไม่ใช้ 96.3% บนสไลด์ผลเฟสสอง |
| การตรวจสัตว์ | Phase 1 slides 11–13: median background/Otsu/morphology/last-seen/rules | รอบจริงใช้ pretrained MegaDetector V5A เป็น presence gate ไม่ใช่ classical pipeline ที่รันครบตามสไลด์เก่า |
| Features และ classifier | Phase2_Content_v2: HOG/appearance+contour features, RF160 trees, 2-stage Active/Inactive | รอบจริง full-frame96×96, frame difference+Farneback 18 features, RF200 trees, Walking/Feeding เท่านั้น |
| การพัก/ไม่เห็นตัว | Phase 1 slide7: hidden is a condition, not a behavior; Phase2_v2: hidden/absent/unclear=Unknown | สอดคล้องกับการคง Unknown ในผลจริง กฎ possible shelter เพิ่มเป็นสมมติฐานอีกคอลัมน์ ไม่เปลี่ยนเป็น observed sleep |
| สถิติรายชั่วโมง/heatmap | สไลด์เดิมเสนอ timeline, heatmap, hourly activity budget/room use | รอบนี้มี hourly sampled-point proposal counts จริง ไม่สร้าง position heatmap/room-use/continuous-duration ที่ไม่มีข้อมูลรองรับ |
| การแบ่งชุดทดสอบ | Phase2_v2: train/validation/test แยก recording group | รอบนี้ยังไม่มี independent held-out test ชัดเจน จึงต้องแก้สไลด์จากแผนเดิมเป็นสิ่งที่ทำจริง |

จำนวน/สัดส่วนของสองชุดไม่จำเป็นต้องใกล้กัน ถ้าบังเอิญใกล้ก็ไม่ใช่หลักฐานว่า mock เดิมถูกต้องหรือโมเดลแม่นยำ

## การประเมินที่มีและไม่มี

Development leave-one-annotation-out รายงาน Feeding29/30 และ Walking5/7 derived segments แต่ช่วงเหล่านี้ใกล้กัน/แชร์เหตุการณ์ จึงไม่ใช่ independent test accuracy อีกการตรวจ Walking ที่เคยเห็นแล้ว 3 คลิป รวม30s ให้ Walking18s และ Unknown12s: 60% เป็น development-check coverage บนคลาสเดียว ไม่ใช่ overall accuracy

ทบทวนภาพหลายเฟรมจาก 53 saved audit clips แบบ convenience sample (7 Feeding, 15 Walking, 31 Unknown): หลาย Walking มีการเปลี่ยนตำแหน่งชัด; บางจุดใกล้ชามอาหารก้ำกึ่ง; ภาพ Feeding ที่บันทึกไว้ยังยืนยันการกินโดยตรงไม่ชัด; Unknown บางจุดมีสัตว์ให้เห็น เช่น A04_20260405041750.mp4 ที่38.75s แสดงว่า detector พลาดได้ การตรวจนี้ไม่ได้ติดป้าย ground truth อิสระครบทุกจุดและไม่ใช้คำนวณ precision

ขั้นต่อไปถ้ามีเวลาคือสุ่ม test clips ที่ไม่ใช้ฝึกและไม่เคยใช้ปรับระบบ ตรวจคนละเหตุการณ์ให้มี Walking/Feeding/visible Rest/Other/Absent แล้วคำนวณ per-class precision/recall/F1 พร้อม support; อย่าฝึกบนข้อมูลทั้งหมดแล้วใช้ชุดเดียวกันรายงาน test accuracy

## สคริปต์พูดสั้น ๆ

“เฟสสองเราฝึกต้นแบบ Random Forest จากตัวอย่างเดินและกินที่ตรวจแล้ว ใช้ MegaDetector ตรวจการปรากฏของสัตว์ และ optical flow อธิบายการเคลื่อนไหว เราประมวลผลตัวอย่างจากวิดีโอครบ31ไฟล์ โดยเลือกช่วง2วินาทีในแต่ละ5นาที รวม1,319มุมกล้อง เมื่อรวมเวลาเดียวกันเหลือ348จุด โมเดลเสนอเดิน53จุด กิน9จุด และ Unknown286จุด ใน Unknown มี198จุดที่ไม่พบสัตว์ครบสี่กล้อง จึงแสดงเป็นอาจอยู่ในที่หลบภายใต้สมมติฐานนาฬิกาตรงกัน ไม่ใช่ยืนยันการนอน ตัวเลขนี้เป็นสัดส่วนผลทำนาย ณ จุดตัวอย่าง ไม่ใช่เวลาจริงทั้งวัน งานยังจำกัดด้วยข้อมูลฝึกน้อย ไม่มีคลาสพัก/นอน และยังไม่มีการทดสอบอิสระ จึงรายงานเป็น pilot พร้อมข้อผิดพลาดที่ตรวจพบ”

## แหล่งอ้างอิงและการตรวจย้อนกลับ

- Repository: https://github.com/Wanikkasit65/civet_project
- โค้ด branch: https://github.com/Wanikkasit65/civet_project/tree/phase2/behavior-pilot-and-tables
- Fast script ที่ใช้: https://github.com/Wanikkasit65/civet_project/blob/1163e2091505f35026d71a53c8eb3b7ce454e469/CMZ_YOLO_Kit/cmz_fast_sample.py
- PR (ยังไม่อ้างว่า merge): https://github.com/Wanikkasit65/civet_project/pull/2
- ข้อมูลต้นทางตามโจทย์: [dataset access supplied separately]
- ผลดิบ: FAST_RESULTS.zip ของผู้ใช้; RESULT_SCOPE.json, BATCH_TRAINING_REPORT.json, SAMPLED_WINDOWS.csv, FUSED_SAMPLED_TIMES.csv, HOURLY_SAMPLED_TIME_TABLE.csv, PER_VIDEO_SAMPLING_TABLE.csv
- Annotation provenance: CMZ_TIMING_CHECK.zip / CHECK_REPORT.json; ลงทะเบียนแยกใน ANNOTATION_REGISTER.csv โดยไม่แก้ label หรือตำแหน่งเวลาเดิม

ไม่ใช้ผลจาก historical wrong-time run แทนผล PTS fast run นี้ ไม่อ้างการรันหลายแสนเฟรมในขั้น scout ว่าเป็นการฝึกหรือการประเมินพฤติกรรมเสร็จแล้ว
