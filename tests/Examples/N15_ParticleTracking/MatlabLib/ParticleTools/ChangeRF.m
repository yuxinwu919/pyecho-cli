function P0=ChangeRF(P0,V1,fi1,V2,fi2,k)
% RF correction
z0=P0(1,1);
P0(:,1)=P0(:,1)-z0;
P0(:,2)=P0(:,2)-V1*cos(k*P0(:,1)+fi1)+V2*cos(k*P0(:,1)+fi2);
P0(:,1)=P0(:,1)+z0;