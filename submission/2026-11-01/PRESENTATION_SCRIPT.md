# CMZ Phase 2: simple English speaking notes

## Slide 1

Good afternoon. Our project uses CCTV video to analyze a civet's behavior. Phase 2 presents a trained pilot, sampled results and an automatic image experiment.

## Slide 2

We study one civet in four connected rooms with four cameras. We keep the Phase 1 goal and behavior definitions. The implementation now uses a pretrained detector and a trained behavior classifier.

## Slide 3

Walking, climbing and feeding belong to Active. Visible resting belongs to Inactive. Our trained pilot supports Walking and Feeding. Hidden, unclear and unsupported cases stay Unknown.

## Slide 4

The historical sampling plan includes all 31 discovered videos. Their 109.84 camera-hours overlap across views of one animal. We process 1,319 short camera windows and combine them into 348 nominal time points.

## Slide 5

First, we decode video using presentation timestamps. MegaDetector proposes animal presence. A Random Forest uses motion features to propose behavior. We preserve uncertain cases and export source-linked tables.

## Slide 6

We retain nine reviewed clips, with 60 seconds Feeding and 14 seconds Walking. They provide 37 derived segments. We calculate 18 motion features and train a Random Forest with 200 trees. Segments from the same events are dependent.

## Slide 7

MegaDetector is a pretrained YOLOv5 animal detector. We did not train a new civet detector. It does not classify eating or sleep. The red outline already exists in these saved images. Yellow shows a new detector proposal.

## Slide 8

We use the same 12 preselected saved images for all settings. At threshold 0.4, raw input 640 detects proposals in one image, while 1280 detects proposals in nine. CLAHE gives eight and gamma gives nine. Existing ROI outlines and possible false positives prevent an accuracy claim.

## Slide 9

The historical plan selects one two-second window in each five-minute interval. That covers about 0.67 percent of the camera footage. We combine matching nominal times, but we do not fill gaps or call Unknown inactive.

## Slide 10

From 348 fused sample points, the model proposes Walking at 53, Feeding at nine, and Unknown at 286. Walking and Feeding give 62 Active proposals. Verified Inactive is unavailable. These are sampled proposals rather than whole-day behavior durations.

## Slide 11

Each hourly bin contains 12 nominal sample times. The peak is nine Active proposals at three in the morning on 5 April. A bin without Active proposals does not prove that the animal was resting.

## Slide 12

The additional control pass includes 53 saved audit clips and 24 windows from one extra original video. All 77 windows complete without processing errors. The 640-input detector finds proposals in ten of 548 sampled frames. This separate image-position plot cannot establish room occupancy.

## Slide 13

The software suite passes 34 tests, and the exported tables agree. A development Walking replay recovers 18 out of 30 seconds. The 60 percent ratio is development recovery, not overall accuracy. Independent behavior precision, recall and F1 remain unavailable.

## Slide 14

The GitHub guide connects each question to evidence. We can open training settings, annotations, raw results and test records directly. Software tests and behavior evaluation have separate links, so we do not confuse their meanings.

## Slide 15

We demonstrate a trained pilot with traceable automatic results. Unknown preserves uncertainty. The current evidence does not establish verified Inactive behavior or a continuous full-day activity budget. Thank you.