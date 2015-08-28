#!/bin/bash
outname=Mission001
echo $outname
cp jmklabseaparams.txt James/$outname.params.txt
python ../emasim.py -a 6416 ./Argo_labsea_ballastinfo.txt hydrographicdata/Labsea_pts_201007until201507.txt ./Labsea$outname.txt 2200000 | tee SimResults/Mission001.out.txt 
cp emasim.pdf SimResults/$outname.pdf
