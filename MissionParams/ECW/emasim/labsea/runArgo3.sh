
outname=LabSea3_50g
python ../emasim.py 6416 ./Argo_labsea2_ballastinfo ./Labsea_pts_201007until201507.txt ./Argo_labsea3_mission.txt 200000 > $outname.txt
mv emasim.pdf $outname.pdf
