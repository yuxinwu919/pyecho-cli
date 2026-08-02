function [Ro]=Particles2Charge(zMeshHead,nz,nr,hz,hr,P)
Np = length(P(:,1));
Ro(1:nz,1:nr)= 0.0;
for i = 1:Np,
    x = P(i,1); y =  P(i,2); z =  P(i,3);
	[fi,ro]=cart2pol(x, y);
	posz = (zMeshHead -z) / hz;
	i0 = floor(posz);
	w0z = i0+1-posz; 
    w1z = 1 - w0z;
	posr = ro / hr-0.5;
	j0 = floor(posr);
	if j0 > -1,
		w0r = j0 + 1 - posr; 
        w1r = 1 - w0r;
	else
		w0r = 0.0; 
        w1r = 1.0;
    end;
    i0=i0+5; j0=j0+2;
	if (i0>-1) && (i0<nz) && (j0<nr),
		Ro(i0,j0) = Ro(i0,j0) + w0r*w0z;
		Ro(i0,j0+1) = Ro(i0,j0+1) + w1r*w0z;
		Ro(i0+1,j0) =Ro(i0+1,j0) + w0r*w1z;
		Ro(i0+1,j0+1) = Ro(i0+1,j0+1) + w1r*w1z;
    end;
 end;

