function P=linac(P,V,fi,lambda)
%P=linac(P,V,fi,lambda)
k=2*pi/lambda;
P(:,2)=P(:,2)+V*cos(k*P(:,1)+fi);