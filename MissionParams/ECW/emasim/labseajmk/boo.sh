#!/bin/bash
outname=LabSea3_50g
echo $outname
rm boo.txt
python ../emasim.py 6416 ./Argo_labsea2_ballastinfo ./Labsea_pts_201007until201507.txt ./Argo_labsea3_mission.txt 20000 | tee boo.txt
