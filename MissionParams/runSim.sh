#!/bin/bash
outname=LabseaMission001
echo $outname
cp $outname.txt SimResults/$outname.params.txt
python ../../emasim/emasim.py -s 40 6416 ./Argo_labsea_ballastinfo.txt hydrographicdata/Labsea_pts_201007until201507.txt ./$outname.txt 2200000 | tee SimResults/$outname.out.txt 
cp emasim.pdf SimResults/$outname.pdf
